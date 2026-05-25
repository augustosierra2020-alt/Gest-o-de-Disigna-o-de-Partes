import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta
import json
import hashlib
from streamlit_gsheets import GSheetsConnection
import extra_streamlit_components as stx
import smtplib
from email.mime.text import MIMEText

# Configuração inicial da página web responsiva
st.set_page_config(page_title="Gestão de Designações e Partes", layout="wide", initial_sidebar_state="expanded")

# --- CONFIGURAÇÃO DE ADMINISTRADOR ---
EMAIL_ADMIN = "augustosierra2020@gmail.com"

# --- FUNÇÃO DE HORÁRIO (BRASÍLIA) ---
def get_horario_brasilia():
    return (datetime.utcnow() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S")

# --- CONEXÃO COM O GOOGLE SHEETS (MÉTODO DIRETO) ---
# Substitua o link abaixo pelo link completo da sua planilha
LINK_DA_PLANILHA = "https://docs.google.com/spreadsheets/d/1z-py9yQJMAwycV0PrmZtloC8Shay6cNwOTMsFOfc8XA/edit?usp=sharing"

def carregar_aba(aba_nome):
    try:
        # Transforma o link normal em um link de exportação de dados direto
        url_csv = LINK_DA_PLANILHA.replace("/edit?usp=sharing", f"/gviz/tq?tqx=out:csv&sheet={aba_nome}")
        return pd.read_csv(url_csv)
    except Exception:
        return pd.DataFrame()

def salvar_aba(df, aba_nome):
    try:
        # Como o Google Cloud está bloqueado, usaremos uma alternativa direta de envio 
        # enviando os comandos formatados ou usando a API simplificada via requests.
        # Para garantir que você não dependa do console do Google Cloud, 
        # vamos usar uma biblioteca que contorna isso usando apenas uma macro do Google Apps Script.
        import requests
        # Vamos configurar a escrita no Passo 3 usando um script de 3 linhas dentro da sua planilha!
        URL_DO_SCRIPT = st.secrets["connections"]["gsheets"].get("script_url", "")
        if URL_DO_SCRIPT:
            payload = {"aba": aba_nome, "dados": df.to_json(orient="records")}
            requests.post(URL_DO_SCRIPT, json=payload)
    except Exception as e:
        st.error(f"Erro ao salvar na nuvem: {e}")

# --- FUNÇÕES DE SEGURANÇA E GERENCIAMENTO DE USUÁRIOS ---
def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def cadastrar_usuario(nome, email, senha):
    df_usuarios = carregar_aba("usuarios")
    
    if not df_usuarios.empty and "email" in df_usuarios.columns:
        email_existe = df_usuarios[df_usuarios["email"].str.lower() == email.lower()]
        nome_existe = df_usuarios[df_usuarios["nome"].str.lower() == nome.lower()]
        
        if not nome_existe.empty:
            return "nome_duplicado"
        if not email_existe.empty:
            return "email_duplicado"
            
    novo_id = 1 if df_usuarios.empty or "id" not in df_usuarios.columns else int(df_usuarios["id"].max()) + 1
    
    novo_registro = pd.DataFrame([{
        "id": novo_id,
        "nome": nome.strip(),
        "email": email.strip().lower(),
        "senha": hash_senha(senha),
        "grupos_json": json.dumps({})
    }])
    
    df_usuarios = pd.concat([df_usuarios, novo_registro], ignore_index=True)
    salvar_aba(df_usuarios, "usuarios")
    return "sucesso"

def verificar_login(email, senha):
    df_usuarios = carregar_aba("usuarios")
    if df_usuarios.empty or "email" not in df_usuarios.columns:
        return None
        
    user = df_usuarios[(df_usuarios["email"].str.lower() == email.lower()) & (df_usuarios["senha"] == hash_senha(senha))]
    if not user.empty:
        return user.iloc[0].to_dict()
    return None

def buscar_usuario_por_id(user_id):
    df_usuarios = carregar_aba("usuarios")
    if df_usuarios.empty or "id" not in df_usuarios.columns:
        return None
    user = df_usuarios[df_usuarios["id"] == int(user_id)]
    if not user.empty:
        return user.iloc[0].to_dict()
    return None

def verificar_email_existe(email):
    df_usuarios = carregar_aba("usuarios")
    if df_usuarios.empty or "email" not in df_usuarios.columns:
        return False
    return not df_usuarios[df_usuarios["email"].str.lower() == email.lower()].empty

def atualizar_senha(email, nova_senha):
    df_usuarios = carregar_aba("usuarios")
    if not df_usuarios.empty and "email" in df_usuarios.columns:
        idx = df_usuarios[df_usuarios["email"].str.lower() == email.lower()].index
        if len(idx) > 0:
            df_usuarios.loc[idx, "senha"] = hash_senha(nova_senha)
            salvar_aba(df_usuarios, "usuarios")

# --- FUNÇÕES EXCLUSIVAS DO ADMIN (PAINEL GOOGLE SHEETS) ---
def listar_todos_usuarios():
    df_usuarios = carregar_aba("usuarios")
    if df_usuarios.empty:
        return pd.DataFrame(columns=["id", "Nome", "Email"])
    return df_usuarios[["id", "nome", "email"]].rename(columns={"nome": "Nome", "email": "Email"})

def listar_todo_historico_admin():
    df_historico = carregar_aba("historico")
    df_usuarios = carregar_aba("usuarios")
    
    if df_historico.empty or df_usuarios.empty:
        return pd.DataFrame()
        
    df_merge = df_historico.merge(df_usuarios, left_on="user_id", right_on="id", suffixes=('_hist', '_user'))
    df_merge = df_merge.sort_values(by="id_hist", ascending=False)
    
    return df_merge[["nome", "email", "grupo", "tarefa", "data_trabalho", "principal", "ajudante", "data_registro"]].rename(
        columns={
            "nome": "Usuário", "email": "Email", "grupo": "Grupo", "tarefa": "Tarefa",
            "data_trabalho": "Data do Evento", "principal": "Principal", "ajudante": "Ajudante", "data_registro": "Salvo em"
        }
    )

def deletar_usuario_admin(user_id):
    df_usuarios = carregar_aba("usuarios")
    df_historico = carregar_aba("historico")
    
    if not df_usuarios.empty:
        df_usuarios = df_usuarios[df_usuarios["id"] != int(user_id)]
        salvar_aba(df_usuarios, "usuarios")
    if not df_historico.empty:
        df_historico = df_historico[df_historico["user_id"] != int(user_id)]
        salvar_aba(df_historico, "historico")

def atualizar_nome_usuario_admin(user_id, novo_nome):
    df_usuarios = carregar_aba("usuarios")
    if not df_usuarios.empty:
        idx = df_usuarios[df_usuarios["id"] == int(user_id)].index
        if len(idx) > 0:
            df_usuarios.loc[idx, "nome"] = novo_nome.strip()
            salvar_aba(df_usuarios, "usuarios")

def salvar_grupos_db(user_id, grupos_dict):
    df_usuarios = carregar_aba("usuarios")
    if not df_usuarios.empty:
        idx = df_usuarios[df_usuarios["id"] == int(user_id)].index
        if len(idx) > 0:
            df_usuarios.loc[idx, "grupos_json"] = json.dumps(grupos_dict)
            salvar_aba(df_usuarios, "usuarios")

def salvar_historico_db(user_id, df_historico_usuario):
    df_global = carregar_aba("historico")
    
    # Remove o histórico antigo do usuário específico para reescrever o atualizado
    if not df_global.empty and "user_id" in df_global.columns:
        df_global = df_global[df_global["user_id"] != int(user_id)]
        
    novos_registros = []
    proximo_id = 1 if df_global.empty or "id" not in df_global.columns else int(df_global["id"].max()) + 1
    
    for _, row in df_historico_usuario.iterrows():
        novos_registros.append({
            "id": proximo_id,
            "user_id": int(user_id),
            "grupo": row['Grupo'],
            "tarefa": row['Tarefa'],
            "data_trabalho": str(row['Data de Trabalho']),
            "principal": row['Principal'],
            "ajudante": row['Ajudante'],
            "data_registro": row.get('Data de Registro', get_horario_brasilia())
        })
        proximo_id += 1
        
    if novos_registros:
        df_novos = pd.DataFrame(novos_registros)
        df_global = pd.concat([df_global, df_novos], ignore_index=True)
        
    salvar_aba(df_global, "historico")

def carregar_historico_db(user_id):
    df_global = carregar_aba("historico")
    if df_global.empty or "user_id" in df_global.columns not in df_global.columns:
        return pd.DataFrame(columns=["Grupo", "Tarefa", "Data de Trabalho", "Principal", "Ajudante", "Data de Registro"])
        
    df_user = df_global[df_global["user_id"] == int(user_id)].copy()
    if df_user.empty:
        return pd.DataFrame(columns=["Grupo", "Tarefa", "Data de Trabalho", "Principal", "Ajudante", "Data de Registro"])
        
    df_user = df_user.rename(columns={
        "grupo": "Grupo", "tarefa": "Tarefa", "data_trabalho": "Data de Trabalho",
        "principal": "Principal", "ajudante": "Ajudante", "data_registro": "Data de Registro"
    })
    df_user["Data de Trabalho"] = pd.to_datetime(df_user["Data de Trabalho"]).dt.date
    return df_user[["Grupo", "Tarefa", "Data de Trabalho", "Principal", "Ajudante", "Data de Registro"]]

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

# --- FUNÇÃO DE RECUPERAÇÃO DE SENHA POR EMAIL ---
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
            st.warning(f"⚠️ **Simulação Ativada**: O código de recuperação enviado para {destinatario} é: **{codigo}**", icon="📧")
            return True
    except Exception as e:
        st.error(f"Erro ao enviar o e-mail: {e}")
        return False

# --- LÓGICA DE GERAÇÃO ALEATÓRIA ---
def gerar_escala_sem_repeticao(membros):
    if len(membros) < 2:
        return None
    principais = membros.copy()
    random.shuffle(principais)
    ajudantes = membros.copy()
    
    tentativas = 0
    while tentatives < 1000:
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

# --- AUTO-LOGIN COOKIE ---
cookie_user_id = cookie_manager.get(cookie="user_id")
if cookie_user_id is not None and st.session_state.user_id is None and not st.session_state.deslogado:
    usuario = buscar_usuario_por_id(int(cookie_user_id))
    if usuario:
        st.session_state.user_id = usuario["id"]
        st.session_state.user_nome = usuario["nome"]
        st.session_state.user_email = usuario["email"]
        st.session_state.grupos = json.loads(usuario["grupos_json"]) if usuario["grupos_json"] else {}
        st.session_state.historico_definitivo = carregar_historico_db(st.session_state.user_id)
        st.rerun()

# --- INTERFACE: TELA DESLOGADO ---
if st.session_state.user_id is None:
    st.title("🔐 Bem-vindo ao Sistema de Designações")
    st.markdown("Faça login ou crie uma conta. Todos os seus dados serão armazenados de forma segura na nuvem.")
    
    aba_login, aba_cadastro = st.tabs(["Entrar", "Criar Conta"])
    
    with aba_login:
        st.subheader("Fazer Login")
        email_login = st.text_input("Email", key="login_email")
        senha_login = st.text_input("Senha", type="password", key="login_senha")
        manter_logado = st.checkbox("Lembrar meu acesso", value=True)
        
        if st.button("Entrar", type="primary", use_container_width=True):
            usuario = verificar_login(email_login, senha_login)
            if usuario:
                st.session_state.user_id = usuario["id"]
                st.session_state.user_nome = usuario["nome"]
                st.session_state.user_email = usuario["email"]
                st.session_state.grupos = json.loads(usuario["grupos_json"]) if usuario["grupos_json"] else {}
                st.session_state.historico_definitivo = carregar_historico_db(st.session_state.user_id)
                st.session_state.deslogado = False 
                
                if manter_logado:
                    validade = datetime.now() + timedelta(days=30)
                    cookie_manager.set("user_id", str(usuario["id"]), expires_at=validade)
                st.rerun()
            else:
                st.error("Email ou senha incorretos.")

        st.write("---")
        with st.expander("Esqueceu sua senha?"):
            if not st.session_state.codigo_validado:
                email_rec = st.text_input("Digite o email cadastrado:", key="input_recuperacao")
                if st.button("Enviar código de confirmação"):
                    if verificar_email_existe(email_rec):
                        codigo = str(random.randint(100000, 999999))
                        st.session_state.codigo_gerado = codigo
                        st.session_state.email_recuperacao = email_rec
                        enviar_codigo_email(email_rec, codigo)
                        st.success("Código enviado!")
                    else:
                        st.error("E-mail não encontrado.")
                
                if st.session_state.codigo_gerado:
                    codigo_inserido = st.text_input("Insira o código de 6 dígitos:")
                    if st.button("Validar Código"):
                        if codigo_inserido == st.session_state.codigo_gerado:
                            st.session_state.codigo_validado = True
                            st.rerun()
                        else:
                            st.error("Código incorreto.")
            else:
                nova_senha_rec = st.text_input("Digite sua nova senha:", type="password")
                if st.button("Redefinir Senha", type="primary"):
                    if nova_senha_rec:
                        atualizar_senha(st.session_state.email_recuperacao, nova_senha_rec)
                        st.success("Senha atualizada!")
                        st.session_state.codigo_gerado = None
                        st.session_state.email_recuperacao = None
                        st.session_state.codigo_validado = False
                    else:
                        st.warning("A senha não pode estar em branco.")
                
    with aba_cadastro:
        st.subheader("Novo Cadastro")
        novo_nome = st.text_input("Nome Completo", key="cad_nome")
        novo_email = st.text_input("Email", key="cad_email")
        nova_senha = st.text_input("Senha", type="password", key="cad_senha")
        
        if st.button("Cadastrar", type="secondary", use_container_width=True):
            if novo_nome and novo_email and nova_senha:
                resultado = cadastrar_usuario(novo_nome, novo_email, nova_senha)
                if resultado == "sucesso":
                    st.success("Conta criada! Faça login na aba ao lado.")
                elif resultado == "nome_duplicado":
                    st.error("⚠️ Este nome já está em uso.")
                elif resultado == "email_duplicado":
                    st.error("⚠️ Este email já está cadastrado.")
            else:
                st.warning("Preencha todos os campos.")

# --- INTERFACE: TELA LOGADO ---
else:
    with st.sidebar:
        st.title(f"Olá, {st.session_state.user_nome} 👋")
        
        email_atual_limpo = st.session_state.user_email.strip().lower() if st.session_state.user_email else ""
        if email_atual_limpo == EMAIL_ADMIN.strip().lower():
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
            try: cookie_manager.delete("user_id")
            except KeyError: pass
            st.session_state.deslogado = True
            st.session_state.user_id = None
            st.session_state.user_nome = None
            st.session_state.user_email = None
            st.rerun()

    # --- PAINEL ADMINISTRADOR ---
    if st.session_state.view_mode == "admin":
        st.title("🛠️ Painel Administrativo Cloud")
        aba_admin_usuarios, aba_admin_historico = st.tabs(["👥 Gerenciar Usuários", "🌎 Ver Histórico Global"])
        
        with aba_admin_usuarios:
            df_usuarios = listar_todos_usuarios()
            if not df_usuarios.empty:
                st.write(f"**Total de usuários cadastrados na nuvem:** {len(df_usuarios)}")
                st.dataframe(df_usuarios, use_container_width=True, hide_index=True)
                
                st.write("---")
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("✏️ Editar Nome")
                    user_id_editar = st.selectbox("Selecione o Usuário:", df_usuarios["Nome"] + " (" + df_usuarios["Email"] + ")", key="sel_edit")
                    novo_nome_admin = st.text_input("Novo Nome:")
                    if st.button("Salvar Alteração"):
                        if novo_nome_admin.strip():
                            idx = df_usuarios[df_usuarios["Nome"] + " (" + df_usuarios["Email"] + ")" == user_id_editar].index[0]
                            atualizar_nome_usuario_admin(int(df_usuarios.loc[idx, "id"]), novo_nome_admin)
                            st.success("Nome atualizado!")
                            st.rerun()
                with col2:
                    st.subheader("🗑️ Remover Usuário")
                    user_id_remover = st.selectbox("Selecione o Usuário a ser apagado:", df_usuarios["Nome"] + " (" + df_usuarios["Email"] + ")", key="sel_del")
                    if st.button("Confirmar Exclusão", type="primary"):
                        idx = df_usuarios[df_usuarios["Nome"] + " (" + df_usuarios["Email"] + ")" == user_id_remover].index[0]
                        id_real = int(df_usuarios.loc[idx, "id"])
                        if df_usuarios.loc[idx, "Email"].strip().lower() == EMAIL_ADMIN.strip().lower():
                            st.error("Você não pode excluir o Administrador principal!")
                        else:
                            deletar_usuario_admin(id_real)
                            st.success("Usuário removido!")
                            st.rerun()
            else:
                st.info("Nenhum usuário cadastrado.")
                
        with aba_admin_historico:
            df_hist_global = listar_todo_historico_admin()
            if not df_hist_global.empty:
                st.dataframe(df_hist_global, use_container_width=True, hide_index=True)
                csv_global = df_hist_global.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Baixar Relatório Global (.csv)", data=csv_global, file_name=f"Relatorio_Geral_{datetime.today().date()}.csv", mime='text/csv')
            else:
                st.info("Nenhum histórico salvo na nuvem ainda.")

    # --- VISÃO SISTEMA PADRÃO ---
    else:
        st.title("👥 Sistema Gestão de Designações")
        aba_gerador, aba_historico, aba_grupos = st.tabs(["🗓️ Gerar e Editar Escala", "📊 Histórico Consolidado", "🗂️ Gestão de Grupos"])

        with aba_gerador:
            st.header("1. Configurar Nova Atividade")
            if not st.session_state.grupos:
                st.warning("Você não tem nenhum grupo cadastrado. Vá até a aba 'Gestão de Grupos' para criar um.")
            else:
                col1, col2 = st.columns([1, 1])
                with col1: grupo_selecionado = st.selectbox("Selecione o Grupo:", list(st.session_state.grupos.keys()))
                with col2: tarefa_nome = st.text_input("Nome da Atividade:", value="Coordenação do Evento")
                    
                if st.button("🔄 Gerar Sugestão de Duplas", type="primary", use_container_width=True):
                    membros = st.session_state.grupos[grupo_selecionado]
                    if len(membros) < 2: st.error("O grupo precisa ter pelo menos 2 pessoas.")
                    else:
                        st.session_state.escala_temporaria = gerar_escala_sem_repeticao(membros)
                        st.toast("Sugestão de duplas gerada!", icon="💡")

                if st.session_state.escala_temporaria is not None:
                    st.write("---")
                    st.subheader("✍️ 2. Área Editável: Ajuste, Adicione ou Remova Duplas")
                    escala_editada = st.data_editor(
                        st.session_state.escala_temporaria,
                        column_config={
                            "Principal": st.column_config.TextColumn("🧑‍✈️ Principal (Líder)", required=True),
                            "Ajudante": st.column_config.TextColumn("🧑‍🔧 Ajudante", required=True),
                            "Data de Trabalho": st.column_config.DateColumn(
                                "📅 Data de Trabalho", min_value=datetime(2026, 1, 1).date(), format="DD/MM/YYYY", required=True
                            )
                        },
                        num_rows="dynamic", hide_index=True, use_container_width=True
                    )
                    
                    if st.button("💾 Confirmar e Registrar no Histórico", type="secondary", use_container_width=True):
                        df_registro = escala_editada.dropna(subset=["Principal", "Ajudante"]).copy()
                        if df_registro.empty: st.warning("A tabela está vazia.")
                        else:
                            df_registro["Grupo"] = grupo_selecionado
                            df_registro["Tarefa"] = tarefa_nome
                            df_registro["Data de Trabalho"] = pd.to_datetime(df_registro["Data de Trabalho"]).dt.date
                            df_registro["Data de Registro"] = get_horario_brasilia()
                            
                            df_registro = df_registro[["Grupo", "Tarefa", "Data de Trabalho", "Principal", "Ajudante", "Data de Registro"]]
                            st.session_state.historico_definitivo = pd.concat([st.session_state.historico_definitivo, df_registro], ignore_index=True)
                            salvar_historico_db(st.session_state.user_id, st.session_state.historico_definitivo)
                            
                            st.session_state.escala_temporaria = None
                            st.success("Escala salva com sucesso na nuvem!")
                            st.rerun()

        with aba_historico:
            st.header("📊 Seu Histórico de Atividades")
            if not st.session_state.historico_definitivo.empty:
                df_exibir = st.session_state.historico_definitivo.sort_values(by="Data de Trabalho", ascending=False).copy()
                df_editado = st.data_editor(
                    df_exibir,
                    column_config={
                        "Tarefa": st.column_config.TextColumn("📝 Tarefa", required=True),
                        "Data de Trabalho": st.column_config.DateColumn("📅 Data de Trabalho", format="DD/MM/YYYY", required=True),
                        "Data de Registro": st.column_config.TextColumn("🕰️ Salvo Em", disabled=True)
                    },
                    use_container_width=True, hide_index=True, key="editor_historico_definitivo"
                )
                
                if not df_editado.equals(st.session_state.historico_definitivo):
                    st.session_state.historico_definitivo = df_editado
                    salvar_historico_db(st.session_state.user_id, st.session_state.historico_definitivo)
                
                st.write("---")
                col_nome, col_baixar, col_limpar = st.columns([2, 1, 1])
                with col_nome: nome_historico = st.text_input("Nome do arquivo de backup:", value="Escala_Geral")
                with col_baixar:
                    st.write(""); st.write("")
                    csv = st.session_state.historico_definitivo.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Baixar Backup (.csv)", data=csv, file_name=f"{nome_historico}.csv", mime='text/csv', use_container_width=True)
                with col_limpar:
                    st.write(""); st.write("")
                    if st.button("🗑️ Limpar Todo o Histórico", use_container_width=True):
                        st.session_state.historico_definitivo = pd.DataFrame(columns=["Grupo", "Tarefa", "Data de Trabalho", "Principal", "Ajudante", "Data de Registro"])
                        salvar_historico_db(st.session_state.user_id, st.session_state.historico_definitivo)
                        st.rerun()
            else: st.info("Nenhum registro confirmado.")

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
                        st.rerun()
            with col_ren_grp:
                if st.session_state.grupos:
                    grupo_a_renomear = st.selectbox("Grupo a Renomear:", list(st.session_state.grupos.keys()), key="select_ren_grp")
                    novo_nome_para_grupo = st.text_input("Novo Nome:", key="input_ren_grp")
                    if st.button("✏️ Confirmar Nome", use_container_width=True):
                        if novo_nome_para_grupo.strip() and novo_nome_para_grupo.strip() not in st.session_state.grupos:
                            st.session_state.grupos[novo_nome_para_grupo.strip()] = st.session_state.grupos.pop(grupo_a_renomear)
                            salvar_grupos_db(st.session_state.user_id, st.session_state.grupos) 
                            st.rerun()
            with col_del_grp:
                if st.session_state.grupos:
                    grupo_a_remover = st.selectbox("Excluir Grupo:", list(st.session_state.grupos.keys()), key="select_del_grp")
                    if st.button("🗑️ Excluir Grupo", use_container_width=True):
                        del st.session_state.grupos[grupo_a_remover]
                        salvar_grupos_db(st.session_state.user_id, st.session_state.grupos) 
                        st.rerun()

            st.write("---")
            st.subheader("2. Visualizar e Editar Integrantes")
            if not st.session_state.grupos: st.info("Você não possui grupos.")
            else:
                grupo_visualizar = st.radio("Selecione o grupo:", list(st.session_state.grupos.keys()), horizontal=True)
                lista_atual = st.session_state.grupos[grupo_visualizar]
                st.write(f"**Integrantes do grupo ({len(lista_atual)} pessoas):**")
                st.dataframe(pd.DataFrame(lista_atual, columns=["Nome do Integrante"]), use_container_width=True, hide_index=True)
                
                st.write("---")
                col_adicionar, col_remover = st.columns([1, 1])
                with col_adicionar:
                    st.markdown("#### ➕ Adicionar integrante:")
                    grupo_destino = st.selectbox("Escolha o grupo:", list(st.session_state.grupos.keys()), key="select_add_destino")
                    novo_nome = st.text_input("Nome da pessoa:", key="input_add_membro")
                    if st.button("Confirmar Adição", type="secondary", use_container_width=True):
                        if novo_nome.strip() and novo_nome.strip() not in st.session_state.grupos[grupo_destino]:
                            st.session_state.grupos[grupo_destino].append(novo_nome.strip())
                            salvar_grupos_db(st.session_state.user_id, st.session_state.grupos) 
                            st.rerun()
                with col_remover:
                    st.markdown("#### 🗑️ Remover integrante:")
                    grupo_origem = st.selectbox("Escolha o grupo:", list(st.session_state.grupos.keys()), key="select_del_destino")
                    lista_remocao = st.session_state.grupos[grupo_origem]
                    if len(lista_remocao) > 0:
                        selecionar_todos = st.checkbox("Selecionar todos", key="chk_sel_all")
                        nomes_remover = st.multiselect("Pessoas:", options=lista_remocao, default=lista_remocao if selecionar_todos else [])
                        if st.button("Confirmar Remoção", type="primary", use_container_width=True) and nomes_remover:
                            for nome in nomes_remover: st.session_state.grupos[grupo_origem].remove(nome)
                            salvar_grupos_db(st.session_state.user_id, st.session_state.grupos) 
                            st.rerun()

        # --- RODAPÉ ---
        st.write("---")
        st.markdown("""<div style="text-align: center; color: #888888; font-size: 12px; padding: 10px 0px;">Criado e atualizado por: Sérgio Sierra</div>""", unsafe_allow_html=True)