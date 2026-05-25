import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
import sqlite3
import json
import hashlib
import extra_streamlit_components as stx
import smtplib
from email.mime.text import MIMEText

# Configuração inicial da página web
st.set_page_config(page_title="Gestão de Designações e Partes", layout="wide", initial_sidebar_state="expanded")

# --- CONFIGURAÇÃO DE ADMINISTRADOR E E-MAIL ---
EMAIL_ADMIN = "augustosierra2020@gmailcom"

# --- FUNÇÃO DE HORÁRIO (BRASÍLIA) ---
def get_horario_brasilia():
    return (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S")

# --- CONEXÃO E CONFIGURAÇÃO DO BANCO DE DADOS (SQLite) ---
def conectar_db():
    conn = sqlite3.connect('banco_de_dados.db', check_same_thread=False)
    return conn

def criar_tabelas():
    conn = conectar_db()
    c = conn.cursor()
    
    # 🔒 GARANTIA DE ISOLAMENTO: Grupos salvos na própria linha do usuário (grupos_json)
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            grupos_json TEXT
        )
    ''')
    
    # 🔒 GARANTIA DE ISOLAMENTO: Todo histórico é carimbado e "amarrado" ao user_id (FOREIGN KEY)
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
    
    c.execute("PRAGMA table_info(historico)")
    colunas_historico = [col[1] for col in c.fetchall()]
    if "data_registro" not in colunas_historico:
        c.execute("ALTER TABLE historico ADD COLUMN data_registro TEXT")
        
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
        c.execute('SELECT nome, email FROM usuarios WHERE lower(nome) = lower(?) OR lower(email) = lower(?)', (nome, email))
        usuario_existente = c.fetchone()
        
        if usuario_existente:
            if usuario_existente[0].lower() == nome.lower():
                return "nome_duplicado"
            if usuario_existente[1].lower() == email.lower():
                return "email_duplicado"

        # Grupos iniciais que cada novo usuário recebe (cada um ganha sua própria cópia independente)
        grupos_padrao = json.dumps({
            "Varões": ["Adriano", "Brayan", "Caio", "Edevaldo", "Jorge", "Pedro", "Rander", "Sergio"],
            "Irmãs": ["Adriana", "Aline", "Anne", "Cassandra", "Daniela", "Debora", "Estela", "Gabrielly", "Letícia"]
        })
        c.execute('INSERT INTO usuarios (nome, email, senha, grupos_json) VALUES (?, ?, ?, ?)', 
                  (nome, email, hash_senha(senha), grupos_padrao))
        conn.commit()
        return "sucesso"
        
    except sqlite3.IntegrityError:
        return "email_duplicado" 
    finally:
        conn.close()

def verificar_login(email, senha):
    conn = conectar_db()
    c = conn.cursor()
    c.execute('SELECT id, nome, email, grupos_json FROM usuarios WHERE email=? AND senha=?', (email, hash_senha(senha)))
    resultado = c.fetchone()
    conn.close()
    return resultado

def buscar_usuario_por_id(user_id):
    conn = conectar_db()
    c = conn.cursor()
    c.execute('SELECT id, nome, email, grupos_json FROM usuarios WHERE id=?', (user_id,))
    resultado = c.fetchone()
    conn.close()
    return resultado

def verificar_email_existe(email):
    conn = conectar_db()
    c = conn.cursor()
    c.execute('SELECT id FROM usuarios WHERE email=?', (email,))
    resultado = c.fetchone()
    conn.close()
    return resultado is not None

def atualizar_senha(email, nova_senha):
    conn = conectar_db()
    c = conn.cursor()
    c.execute('UPDATE usuarios SET senha = ? WHERE email = ?', (hash_senha(nova_senha), email))
    conn.commit()
    conn.close()

# --- FUNÇÕES EXCLUSIVAS DO ADMIN ---
def listar_todos_usuarios():
    conn = conectar_db()
    df = pd.read_sql_query('SELECT id, nome as Nome, email as Email FROM usuarios', conn)
    conn.close()
    return df

def listar_todo_historico_admin():
    conn = conectar_db()
    query = '''
        SELECT u.nome as "Usuário", u.email as "Email",
               h.grupo as "Grupo", h.tarefa as "Tarefa", 
               h.data_trabalho as "Data do Evento", 
               h.principal as "Principal", h.ajudante as "Ajudante", 
               h.data_registro as "Salvo em (Brasília)"
        FROM historico h
        JOIN usuarios u ON h.user_id = u.id
        ORDER BY h.id DESC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def deletar_usuario_admin(user_id):
    conn = conectar_db()
    c = conn.cursor()
    c.execute('DELETE FROM historico WHERE user_id = ?', (user_id,))
    c.execute('DELETE FROM usuarios WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

def atualizar_nome_usuario_admin(user_id, novo_nome):
    conn = conectar_db()
    c = conn.cursor()
    c.execute('UPDATE usuarios SET nome = ? WHERE id = ?', (novo_nome, user_id))
    conn.commit()
    conn.close()

# 🔒 GARANTIA DE ISOLAMENTO: Grupos salvos EXCLUSIVAMENTE para o ID logado
def salvar_grupos_db(user_id, grupos_dict):
    conn = conectar_db()
    c = conn.cursor()
    c.execute('UPDATE usuarios SET grupos_json = ? WHERE id = ?', (json.dumps(grupos_dict), user_id))
    conn.commit()
    conn.close()

# 🔒 GARANTIA DE ISOLAMENTO: Apaga e reescreve histórico EXCLUSIVAMENTE do ID logado
def salvar_historico_db(user_id, df_historico):
    conn = conectar_db()
    conn.execute('DELETE FROM historico WHERE user_id = ?', (user_id,))
    for index, row in df_historico.iterrows():
        data_reg = row.get('Data de Registro', get_horario_brasilia())
        conn.execute('''
            INSERT INTO historico (user_id, grupo, tarefa, data_trabalho, principal, ajudante, data_registro)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, row['Grupo'], row['Tarefa'], str(row['Data de Trabalho']), row['Principal'], row['Ajudante'], str(data_reg)))
    conn.commit()
    conn.close()

# 🔒 GARANTIA DE ISOLAMENTO: Carrega o histórico EXCLUSIVAMENTE do ID logado
def carregar_historico_db(user_id):
    conn = conectar_db()
    df = pd.read_sql_query(
        'SELECT grupo as Grupo, tarefa as Tarefa, data_trabalho as "Data de Trabalho", principal as Principal, ajudante as Ajudante, data_registro as "Data de Registro" FROM historico WHERE user_id = ?', 
        conn,
        params=(user_id,)
    )
    conn.close()
    if not df.empty:
        df["Data de Trabalho"] = pd.to_datetime(df["Data de Trabalho"]).dt.date
    return df

# --- POP-UP DE AUTENTICAÇÃO DO ADMIN ---
@st.dialog("🔒 Autenticação Restrita")
def pop_up_senha_adm():
    st.write("Por favor, insira a Senha do ADM para acessar o painel administrativo.")
    senha_inserida = st.text_input("Senha do ADM:", type="password")
    
    if st.button("Confirmar Acesso", type="primary", use_container_width=True):
        if senha_inserida == "admsergio25":
            st.session_state.view_mode = "admin"
            st.rerun()
        else:
            st.error("Senha incorreta! Acesso negado.")

# --- FUNÇÃO DE ENVIO DE E-MAIL (RECUPERAÇÃO DE SENHA) ---
def enviar_codigo_email(destinatario, codigo):
    EMAIL_REMETENTE = "" 
    SENHA_APP = "" 
    
    try:
        if EMAIL_REMETENTE and SENHA_APP:
            msg = MIMEText(f"Seu código de recuperação de senha é: {codigo}")
            msg['Subject'] = "Recuperação de Senha - Sistema de Designações"
            msg['From'] = EMAIL_REMETENTE
            msg['To'] = destinatario
            
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(EMAIL_REMETENTE, SENHA_APP)
                server.send_message(msg)
            return True
        else:
            st.warning(f"⚠️ **Simulação Ativada (Falta configuração SMTP)**: O código enviado para o email {destinatario} é: **{codigo}**", icon="📧")
            return True
    except Exception as e:
        st.error(f"Erro ao enviar o e-mail: {e}")
        return False

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
cookie_manager = stx.CookieManager(key="gerenciador_cookies")

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_nome" not in st.session_state:
    st.session_state.user_nome = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "app" 
if "escala_temporaria" not in st.session_state:
    st.session_state.escala_temporaria = None
if "codigo_gerado" not in st.session_state:
    st.session_state.codigo_gerado = None
if "email_recuperacao" not in st.session_state:
    st.session_state.email_recuperacao = None
if "codigo_validado" not in st.session_state:
    st.session_state.codigo_validado = False
if "deslogado" not in st.session_state:
    st.session_state.deslogado = False

# --- LÓGICA DE AUTO-LOGIN ---
cookie_user_id = cookie_manager.get(cookie="user_id")
if cookie_user_id is not None and st.session_state.user_id is None and not st.session_state.deslogado:
    usuario = buscar_usuario_por_id(int(cookie_user_id))
    if usuario:
        st.session_state.user_id = usuario[0]
        st.session_state.user_nome = usuario[1]
        st.session_state.user_email = usuario[2]
        
        # 🔒 GARANTIA DE ISOLAMENTO: Carrega os grupos daquele ID específico
        st.session_state.grupos = json.loads(usuario[3]) if usuario[3] else {}
        # 🔒 GARANTIA DE ISOLAMENTO: Carrega o histórico daquele ID específico
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
        
        manter_logado = st.checkbox("Lembrar meu acesso", value=True)
        
        if st.button("Entrar", type="primary"):
            usuario = verificar_login(email_login, senha_login)
            if usuario:
                st.session_state.user_id = usuario[0]
                st.session_state.user_nome = usuario[1]
                st.session_state.user_email = usuario[2]
                st.session_state.grupos = json.loads(usuario[3]) if usuario[3] else {}
                st.session_state.historico_definitivo = carregar_historico_db(st.session_state.user_id)
                st.session_state.deslogado = False 
                
                if manter_logado:
                    validade = datetime.now() + timedelta(days=30)
                    cookie_manager.set("user_id", str(usuario[0]), expires_at=validade)
                
                st.rerun()
            else:
                st.error("Email ou senha incorretos.")

        st.write("---")
        
        with st.expander("Esqueceu sua senha?"):
            if not st.session_state.codigo_validado:
                email_rec = st.text_input("Digite o email cadastrado para recuperação:", key="input_recuperacao")
                if st.button("Enviar código de confirmação"):
                    if verificar_email_existe(email_rec):
                        codigo = str(random.randint(100000, 999999))
                        st.session_state.codigo_gerado = codigo
                        st.session_state.email_recuperacao = email_rec
                        enviar_codigo_email(email_rec, codigo)
                        st.success("Código enviado! Verifique seu e-mail (e a caixa de spam).")
                    else:
                        st.error("E-mail não encontrado na base de dados.")
                
                if st.session_state.codigo_gerado:
                    codigo_inserido = st.text_input("Insira o código de 6 dígitos recebido:")
                    if st.button("Validar Código"):
                        if codigo_inserido == st.session_state.codigo_gerado:
                            st.session_state.codigo_validado = True
                            st.success("Código validado! Você já pode criar uma nova senha abaixo.")
                            st.rerun()
                        else:
                            st.error("Código incorreto.")
            else:
                st.success(f"Recuperando acesso para: **{st.session_state.email_recuperacao}**")
                nova_senha_rec = st.text_input("Digite sua nova senha:", type="password", key="nova_senha_rec")
                if st.button("Redefinir Senha", type="primary"):
                    if nova_senha_rec:
                        atualizar_senha(st.session_state.email_recuperacao, nova_senha_rec)
                        st.success("Senha atualizada com sucesso! Você já pode fazer login.")
                        st.session_state.codigo_gerado = None
                        st.session_state.email_recuperacao = None
                        st.session_state.codigo_validado = False
                    else:
                        st.warning("A senha não pode estar em branco.")
                
    with aba_cadastro:
        st.subheader("Novo Cadastro")
        novo_nome = st.text_input("Nome Completo / Usuário", key="cad_nome")
        novo_email = st.text_input("Email", key="cad_email")
        nova_senha = st.text_input("Senha", type="password", key="cad_senha")
        
        if st.button("Cadastrar", type="secondary"):
            if novo_nome and novo_email and nova_senha:
                resultado = cadastrar_usuario(novo_nome, novo_email, nova_senha)
                
                if resultado == "sucesso":
                    st.success("Conta criada com sucesso! Faça login na aba ao lado.")
                elif resultado == "nome_duplicado":
                    st.error("⚠️ Este nome de usuário já está em uso. Por favor, escolha outro.")
                elif resultado == "email_duplicado":
                    st.error("⚠️ Este email já está cadastrado. Tente fazer login.")
            else:
                st.warning("Preencha todos os campos antes de cadastrar.")

# --- ÁREA LOGADA DO SISTEMA ---
else:
    with st.sidebar:
        st.title(f"Olá, {st.session_state.user_nome} 👋")
        st.write("Seus dados estão protegidos e isolados.")
        
        email_atual_limpo = st.session_state.user_email.strip().lower() if st.session_state.user_email else ""
        email_admin_limpo = EMAIL_ADMIN.strip().lower()
        
        if email_atual_limpo == email_admin_limpo:
            st.write("---")
            if st.session_state.view_mode == "app":
                if st.button("🛠️ Sala do Adm", use_container_width=True, type="primary"):
                    pop_up_senha_adm() 
            else:
                if st.button("🏠 Voltar para o Sistema", use_container_width=True, type="primary"):
                    st.session_state.view_mode = "app"
                    st.rerun()
            st.write("---")
            
        if st.button("🚪 Sair (Logout)", use_container_width=True):
            try:
                cookie_manager.delete("user_id")
            except KeyError:
                pass
            
            st.session_state.deslogado = True
            st.session_state.user_id = None
            st.session_state.user_nome = None
            st.session_state.user_email = None
            st.rerun()

    # ========================================================
    # VISÃO ADMINISTRADOR
    # ========================================================
    if st.session_state.view_mode == "admin":
        st.title("🛠️ Painel Administrativo")
        
        aba_admin_usuarios, aba_admin_historico = st.tabs(["👥 Gerenciar Usuários", "🌎 Ver Histórico Global"])
        
        with aba_admin_usuarios:
            st.markdown("Bem-vindo à área de administração. Aqui você pode gerenciar os usuários do sistema.")
            df_usuarios = listar_todos_usuarios()
            
            if not df_usuarios.empty:
                st.write(f"**Total de usuários cadastrados:** {len(df_usuarios)}")
                st.dataframe(df_usuarios, use_container_width=True, hide_index=True)
                
                st.write("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("✏️ Editar Nome de Usuário")
                    user_id_editar = st.selectbox("Selecione o Usuário:", df_usuarios["Nome"] + " (" + df_usuarios["Email"] + ")", key="sel_edit")
                    novo_nome_admin = st.text_input("Novo Nome:")
                    
                    if st.button("Salvar Alteração"):
                        if novo_nome_admin.strip():
                            idx = df_usuarios[df_usuarios["Nome"] + " (" + df_usuarios["Email"] + ")" == user_id_editar].index[0]
                            id_real = int(df_usuarios.loc[idx, "id"])
                            atualizar_nome_usuario_admin(id_real, novo_nome_admin)
                            st.success("Nome atualizado com sucesso!")
                            st.rerun()
                        else:
                            st.warning("Digite um nome válido.")

                with col2:
                    st.subheader("🗑️ Remover Usuário")
                    user_id_remover = st.selectbox("Selecione o Usuário a ser apagado:", df_usuarios["Nome"] + " (" + df_usuarios["Email"] + ")", key="sel_del")
                    
                    st.warning("⚠️ Atenção: Isso apagará o usuário e todo o histórico dele de forma permanente.")
                    if st.button("Confirmar Exclusão", type="primary"):
                        idx = df_usuarios[df_usuarios["Nome"] + " (" + df_usuarios["Email"] + ")" == user_id_remover].index[0]
                        id_real = int(df_usuarios.loc[idx, "id"])
                        email_excluido = df_usuarios.loc[idx, "Email"]
                        
                        if email_excluido.strip().lower() == email_admin_limpo:
                            st.error("Você não pode excluir o Administrador principal do sistema!")
                        else:
                            deletar_usuario_admin(id_real)
                            st.success("Usuário removido com sucesso!")
                            st.rerun()
            else:
                st.info("Nenhum usuário encontrado.")
                
        with aba_admin_historico:
            st.markdown("Acompanhe aqui tudo o que foi salvo por cada usuário do sistema (Horário de Brasília).")
            df_hist_global = listar_todo_historico_admin()
            
            if not df_hist_global.empty:
                st.dataframe(df_hist_global, use_container_width=True, hide_index=True)
                
                csv_global = df_hist_global.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Baixar Relatório Global (.csv)", data=csv_global, file_name=f"Auditoria_Geral_{datetime.today().date()}.csv", mime='text/csv')
            else:
                st.info("Nenhum usuário salvou históricos ainda.")

    # ========================================================
    # VISÃO PADRÃO (SISTEMA)
    # ========================================================
    else:
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
                            
                            df_registro["Data de Registro"] = get_horario_brasilia()
                            
                            df_registro = df_registro[["Grupo", "Tarefa", "Data de Trabalho", "Principal", "Ajudante", "Data de Registro"]]
                            
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
                        "Data de Trabalho": st.column_config.DateColumn("📅 Data de Trabalho", format="DD/MM/YYYY", required=True),
                        "Data de Registro": st.column_config.TextColumn("🕰️ Salvo Em", disabled=True)
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
                        st.session_state.historico_definitivo = pd.DataFrame(columns=["Grupo", "Tarefa", "Data de Trabalho", "Principal", "Ajudante", "Data de Registro"])
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