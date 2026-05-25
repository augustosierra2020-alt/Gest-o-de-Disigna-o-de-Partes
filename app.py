import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
import sqlite3
import json
import hashlib
import extra_streamlit_components as stx

# Configuração inicial da página web
st.set_page_config(page_title="Gestão de Designações e Partes", layout="wide", initial_sidebar_state="expanded")

# --- CONEXÃO E CONFIGURAÇÃO DO BANCO DE DADOS (SQLite) ---
def conectar_db():
    conn = sqlite3.connect('banco_de_dados.db', check_same_thread=False)
    return conn

def criar_tabelas():
    conn = conectar_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            grupos_json TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            grupo TEXT,
            tarefa TEXT,
            data_trabalho TEXT,
            principal TEXT,
            ajudante TEXT,
            FOREIGN KEY(user_id) REFERENCES usuarios(id)
        )
    ''')
    conn.commit()
    conn.close()

criar_tabelas()

# --- FUNÇÕES DE SEGURANÇA E BANCO DE DADOS ---
def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def cadastrar_usuario(nome, email, senha):
    conn = conectar_db()
    c = conn.cursor()
    try:
        grupos_padrao = json.dumps({
            "Varões": ["Adriano", "Brayan", "Caio", "Edevaldo", "Jorge", "Pedro", "Rander", "Sergio"],
            "Irmãs": ["Adriana", "Aline", "Anne", "Cassandra", "Daniela", "Debora", "Estela", "Gabrielly", "Letícia"]
        })
        c.execute('INSERT INTO usuarios (nome, email, senha, grupos_json) VALUES (?, ?, ?, ?)', 
                  (nome, email, hash_senha(senha), grupos_padrao))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False 
    finally:
        conn.close()

def verificar_login(email, senha):
    conn = conectar_db()
    c = conn.cursor()
    c.execute('SELECT id, nome, grupos_json FROM usuarios WHERE email=? AND senha=?', (email, hash_senha(senha)))
    resultado = c.fetchone()
    conn.close()
    return resultado

def buscar_usuario_por_id(user_id):
    conn = conectar_db()
    c = conn.cursor()
    c.execute('SELECT id, nome, grupos_json FROM usuarios WHERE id=?', (user_id,))
    resultado = c.fetchone()
    conn.close()
    return resultado

def salvar_grupos_db(user_id, grupos_dict):
    conn = conectar_db()
    c = conn.cursor()
    c.execute('UPDATE usuarios SET grupos_json = ? WHERE id = ?', (json.dumps(grupos_dict), user_id))
    conn.commit()
    conn.close()

def salvar_historico_db(user_id, df_historico):
    conn = conectar_db()
    conn.execute('DELETE FROM historico WHERE user_id = ?', (user_id,))
    for index, row in df_historico.iterrows():
        conn.execute('''
            INSERT INTO historico (user_id, grupo, tarefa, data_trabalho, principal, ajudante)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, row['Grupo'], row['Tarefa'], str(row['Data de Trabalho']), row['Principal'], row['Ajudante']))
    conn.commit()
    conn.close()

def carregar_historico_db(user_id):
    conn = conectar_db()
    df = pd.read_sql_query('SELECT grupo as Grupo, tarefa as Tarefa, data_trabalho as "Data de Trabalho", principal as Principal, ajudante as Ajudante FROM historico WHERE user_id = ?', conn)
    conn.close()
    if not df.empty:
        df["Data de Trabalho"] = pd.to_datetime(df["Data de Trabalho"]).dt.date
    return df

# --- FUNÇÃO LÓGICA DE ESCALA ---
def gerar_escala_sem_repeticao(membros):
    if len(membros) < 2:
        return None
    principais = membros.copy()
    random.shuffle(principais)
    ajudantes = membros.copy()
    
    tentativas = 0
    while tentativas < 1000:
        random.shuffle(ajudantes)
        valido = True
        for p, a in zip(principais, ajudantes):
            if p == a:
                valido = False
                break
        if valido:
            break
        tentativas += 1
        
    escala = []
    for p, a in zip(principais, ajudantes):
        escala.append({
            "Principal": p,
            "Ajudante": a,
            "Data de Trabalho": datetime.today().date()
        })
    random.shuffle(escala)
    return pd.DataFrame(escala)

# --- GERENCIAMENTO DE SESSÃO E COOKIES ---
@st.cache_resource(experimental_allow_widgets=True)
def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_nome" not in st.session_state:
    st.session_state.user_nome = None
if "escala_temporaria" not in st.session_state:
    st.session_state.escala_temporaria = None

# --- LÓGICA DE AUTO-LOGIN ---
# Verifica se há um cookie válido e o usuário ainda não está na sessão
cookie_user_id = cookie_manager.get(cookie="user_id")
if cookie_user_id is not None and st.session_state.user_id is None:
    usuario = buscar_usuario_por_id(int(cookie_user_id))
    if usuario:
        st.session_state.user_id = usuario[0]
        st.session_state.user_nome = usuario[1]
        st.session_state.grupos = json.loads(usuario[2]) if usuario[2] else {}
        st.session_state.historico_definitivo = carregar_historico_db(st.session_state.user_id)
        st.rerun()

# --- TELA DE LOGIN E CADASTRO ---
if st.session_state.user_id is None:
    st.title("🔐 Bem-vindo ao Sistema de Designações")
    st.markdown("Faça login ou crie uma conta para manter seus dados salvos e isolados.")
    
    aba_login, aba_cadastro = st.tabs(["Entrar", "Criar Conta"])
    
    with aba_login:
        st.subheader("Fazer Login")
        email_login = st.text_input("Email", key="login_email")
        senha_login = st.text_input("Senha", type="password", key="login_senha")
        
        # Checkbox opcional para o usuário decidir se quer se manter logado
        manter_logado = st.checkbox("Lembrar meu acesso", value=True)
        
        if st.button("Entrar", type="primary"):
            usuario = verificar_login(email_login, senha_login)
            if usuario:
                st.session_state.user_id = usuario[0]
                st.session_state.user_nome = usuario[1]
                st.session_state.grupos = json.loads(usuario[2]) if usuario[2] else {}
                st.session_state.historico_definitivo = carregar_historico_db(st.session_state.user_id)
                
                # Configura o cookie se ele escolheu se manter logado (validade de 30 dias)
                if manter_logado:
                    validade = datetime.now() + timedelta(days=30)
                    cookie_manager.set("user_id", str(usuario[0]), expires_at=validade)
                
                st.rerun()
            else:
                st.error("Email ou senha incorretos.")
                
    with aba_cadastro:
        st.subheader("Novo Cadastro")
        novo_nome = st.text_input("Nome Completo")
        novo_email = st.text_input("Email")
        nova_senha = st.text_input("Senha", type="password")
        if st.button("Cadastrar", type="secondary"):
            if novo_nome and novo_email and nova_senha:
                sucesso = cadastrar_usuario(novo_nome, novo_email, nova_senha)
                if sucesso:
                    st.success("Conta criada com sucesso! Faça login na aba ao lado.")
                else:
                    st.error("Este email já está cadastrado.")
            else:
                st.warning("Preencha todos os campos.")

# --- ÁREA LOGADA DO SISTEMA ---
else:
    with st.sidebar:
        st.title(f"Olá, {st.session_state.user_nome} 👋")
        st.write("Seus dados estão protegidos e isolados.")
        if st.button("🚪 Sair (Logout)", use_container_width=True):
            # Deleta o cookie para não fazer login automático na próxima vez
            cookie_manager.delete("user_id")
            
            # Limpa tudo da memória
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    st.title("👥 Sistema Gestão de Designações")
    st.markdown("Gerencie seus grupos, edite datas de trabalho e mantenha o controle total do seu histórico.")

    aba_gerador, aba_historico, aba_grupos = st.tabs(["🗓️ Gerar e Editar Escala", "📊 Histórico Consolidado", "🗂️ Gestão de Grupos"])

    # --- ABA 1: GERAR E EDITAR ESCALA ---
    with aba_gerador:
        st.header("1. Configurar Nova Atividade")
        
        if not st.session_state.grupos:
            st.warning("Você não tem nenhum grupo cadastrado. Vá até a aba 'Gestão de Grupos' para criar um.")
        else:
            col1, col2 = st.columns([1, 1])
            with col1:
                grupo_selecionado = st.selectbox("Selecione o Grupo:", list(st.session_state.grupos.keys()))
            with col2:
                tarefa_nome = st.text_input("Nome da Tarefa/Atividade:", value="Coordenação do Evento")
                
            if st.button("🔄 Gerar Sugestão de Duplas", type="primary", use_container_width=True):
                membros = st.session_state.grupos[grupo_selecionado]
                if len(membros) < 2:
                    st.error("O grupo precisa ter pelo menos 2 pessoas.")
                else:
                    st.session_state.escala_temporaria = gerar_escala_sem_repeticao(membros)
                    st.toast("Sugestão de duplas gerada! Ajuste as datas abaixo.", icon="💡")

            if st.session_state.escala_temporaria is not None:
                st.write("---")
                st.subheader("✍️ 2. Área Editável: Ajuste, Adicione ou Remova Duplas")
                
                escala_editada = st.data_editor(
                    st.session_state.escala_temporaria,
                    column_config={
                        "Principal": st.column_config.TextColumn("🧑‍✈️ Principal (Líder)", required=True),
                        "Ajudante": st.column_config.TextColumn("🧑‍🔧 Ajudante", required=True),
                        "Data de Trabalho": st.column_config.DateColumn(
                            "📅 Data de Trabalho",
                            min_value=datetime(2026, 1, 1).date(),
                            format="DD/MM/YYYY",
                            required=True
                        )
                    },
                    num_rows="dynamic",
                    hide_index=True,
                    use_container_width=True
                )
                
                if st.button("💾 Confirmar e Registrar no Histórico", type="secondary", use_container_width=True):
                    df_registro = escala_editada.dropna(subset=["Principal", "Ajudante"])
                    
                    if df_registro.empty:
                        st.warning("A tabela está vazia. Gere uma sugestão ou adicione linhas antes de salvar.")
                    else:
                        df_registro["Grupo"] = grupo_selecionado
                        df_registro["Tarefa"] = tarefa_nome
                        df_registro["Data de Trabalho"] = pd.to_datetime(df_registro["Data de Trabalho"]).dt.date
                        df_registro = df_registro[["Grupo", "Tarefa", "Data de Trabalho", "Principal", "Ajudante"]]
                        
                        st.session_state.historico_definitivo = pd.concat(
                            [st.session_state.historico_definitivo, df_registro], 
                            ignore_index=True
                        )
                        salvar_historico_db(st.session_state.user_id, st.session_state.historico_definitivo)
                        
                        st.session_state.escala_temporaria = None
                        st.success("Sucesso! Escala salva no seu Histórico Consolidado pessoal.")
                        st.rerun()

    # --- ABA 2: HISTÓRICO CONSOLIDADO ---
    with aba_historico:
        st.header("📊 Seu Histórico de Atividades")
        
        if not st.session_state.historico_definitivo.empty:
            st.markdown("✍️ **Edite o histórico abaixo:** Clique duplo para alterar a **Tarefa** ou a **Data**.")
            
            df_exibir = st.session_state.historico_definitivo.sort_values(by="Data de Trabalho", ascending=False).copy()
            
            df_editado = st.data_editor(
                df_exibir,
                column_config={
                    "Tarefa": st.column_config.TextColumn("📝 Tarefa", required=True),
                    "Data de Trabalho": st.column_config.DateColumn("📅 Data de Trabalho", format="DD/MM/YYYY", required=True)
                },
                use_container_width=True,
                hide_index=True,
                key="editor_historico_definitivo"
            )
            
            if not df_editado.equals(st.session_state.historico_definitivo):
                st.session_state.historico_definitivo = df_editado
                salvar_historico_db(st.session_state.user_id, st.session_state.historico_definitivo)
            
            st.write("---")
            st.subheader("💾 Salvar Backup e Limpar")
            
            col_nome, col_baixar, col_limpar = st.columns([2, 1, 1])
            
            with col_nome:
                nome_historico = st.text_input("Nome da Tarefa/Atividade para o arquivo:", value="Escala_Geral")
                data_hoje = datetime.now().strftime("%d-%m-%Y")
                nome_arquivo_csv = f"Historico_{nome_historico}_{data_hoje}.csv"
                
            with col_baixar:
                st.write("")
                st.write("")
                csv = st.session_state.historico_definitivo.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Baixar Backup (.csv)", data=csv, file_name=nome_arquivo_csv, mime='text/csv', use_container_width=True)
                
            with col_limpar:
                st.write("")
                st.write("")
                if st.button("🗑️ Limpar Todo o Histórico", use_container_width=True):
                    st.session_state.historico_definitivo = pd.DataFrame(columns=["Grupo", "Tarefa", "Data de Trabalho", "Principal", "Ajudante"])
                    salvar_historico_db(st.session_state.user_id, st.session_state.historico_definitivo)
                    st.success("Seu histórico foi limpo!")
                    st.rerun()
        else:
            st.info("Você ainda não tem nenhum registro confirmado.")

    # --- ABA 3: GESTÃO DE GRUPOS ---
    with aba_grupos:
        st.header("🗂️ Gestão de Grupos e Integrantes")
        
        st.subheader("1. Gerenciar Grupos")
        col_add_grp, col_ren_grp, col_del_grp = st.columns(3)
        
        with col_add_grp:
            novo_grupo_nome = st.text_input("Criar Novo Grupo:", key="input_add_grp")
            if st.button("➕ Adicionar Grupo", use_container_width=True):
                if novo_grupo_nome.strip() and novo_grupo_nome.strip() not in st.session_state.grupos:
                    st.session_state.grupos[novo_grupo_nome.strip()] = []
                    salvar_grupos_db(st.session_state.user_id, st.session_state.grupos) 
                    st.success("Grupo criado!")
                    st.rerun()
                    
        with col_ren_grp:
            if st.session_state.grupos:
                grupo_a_renomear = st.selectbox("Grupo a Renomear:", list(st.session_state.grupos.keys()), key="select_ren_grp")
                novo_nome_para_grupo = st.text_input("Novo Nome:", key="input_ren_grp")
                if st.button("✏️ Confirmar Nome", use_container_width=True):
                    if novo_nome_para_grupo.strip() and novo_nome_para_grupo.strip() not in st.session_state.grupos:
                        st.session_state.grupos[novo_nome_para_grupo.strip()] = st.session_state.grupos.pop(grupo_a_renomear)
                        salvar_grupos_db(st.session_state.user_id, st.session_state.grupos) 
                        st.success("Grupo renomeado!")
                        st.rerun()

        with col_del_grp:
            if st.session_state.grupos:
                grupo_a_remover = st.selectbox("Excluir Grupo:", list(st.session_state.grupos.keys()), key="select_del_grp")
                if st.button("🗑️ Excluir Grupo", use_container_width=True):
                    del st.session_state.grupos[grupo_a_remover]
                    salvar_grupos_db(st.session_state.user_id, st.session_state.grupos) 
                    st.success("Grupo excluído!")
                    st.rerun()

        st.write("---")

        st.subheader("2. Visualizar e Editar Integrantes")
        if not st.session_state.grupos:
            st.info("Você não possui grupos. Crie um acima.")
        else:
            grupo_visualizar = st.radio("Visualizar lista de integrantes:", list(st.session_state.grupos.keys()), horizontal=True)
            lista_atual = st.session_state.grupos[grupo_visualizar]
            
            st.write(f"**Integrantes do grupo '{grupo_visualizar}' ({len(lista_atual)} pessoas):**")
            st.dataframe(pd.DataFrame(lista_atual, columns=["Nome do Integrante"]), use_container_width=True, hide_index=True)
            
            st.write("---")
            col_adicionar, col_remover = st.columns([1, 1])
            
            with col_adicionar:
                st.markdown("#### ➕ Adicionar integrante em:")
                grupo_destino = st.selectbox("Escolha o grupo de destino:", list(st.session_state.grupos.keys()), key="select_add_destino")
                novo_nome = st.text_input("Nome da pessoa para adicionar:", key="input_add_membro")
                if st.button("Confirmar Adição", type="secondary", use_container_width=True):
                    if novo_nome.strip() and novo_nome.strip() not in st.session_state.grupos[grupo_destino]:
                        st.session_state.grupos[grupo_destino].append(novo_nome.strip())
                        salvar_grupos_db(st.session_state.user_id, st.session_state.grupos) 
                        st.success("Adicionado com sucesso!")
                        st.rerun()
                        
            with col_remover:
                st.markdown("#### 🗑️ Remover do Grupo:")
                grupo_origem = st.selectbox("Escolha o grupo:", list(st.session_state.grupos.keys()), key="select_del_destino")
                lista_remocao = st.session_state.grupos[grupo_origem]
                
                if len(lista_remocao) > 0:
                    selecionar_todos = st.checkbox("Selecionar todos", key="chk_sel_all")
                    selecao = lista_remocao if selecionar_todos else []
                    nomes_remover = st.multiselect("Pessoas para remover:", options=lista_remocao, default=selecao)
                    if st.button("Confirmar Remoção", type="primary", use_container_width=True) and nomes_remover:
                        for nome in nomes_remover:
                            st.session_state.grupos[grupo_origem].remove(nome)
                        salvar_grupos_db(st.session_state.user_id, st.session_state.grupos) 
                        st.success("Removido(s) com sucesso!")
                        st.rerun()

    # --- RODAPÉ ---
    st.write("---")
    st.markdown(
        """<div style="text-align: center; color: #888888; font-size: 12px; padding: 10px 0px;">Criado e atualizado por: Sérgio Sierra</div>""", 
        unsafe_allow_html=True
    )