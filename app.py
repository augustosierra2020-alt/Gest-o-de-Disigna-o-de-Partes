import streamlit as st
import pandas as pd
import random
from datetime import datetime

# Configuração inicial da página web - layout wide adapta-se dinamicamente ao container do navegador
st.set_page_config(page_title="Gestão de Designações e Partes", layout="wide", initial_sidebar_state="collapsed")

# --- BANCO DE DADOS EM MEMÓRIA (Session State) ---
if "grupos" not in st.session_state:
    st.session_state.grupos = {
        "Varões": ["Adriano", "Brayan", "Caio", "Edevaldo", "Jorge", "Pedro", "Rander", "Sergio"],
        "Irmãs": ["Adriana", "Aline", "Anne", "Cassandra", "Daniela", "Debora", "Estela", "Gabrielly", "Letícia", "Lídia", "Lucinda", "Ticinara", "Talita", "Vanderleia"]
    }

# Guarda a escala que acabou de ser gerada temporariamente para edição
if "escala_temporaria" not in st.session_state:
    st.session_state.escala_temporaria = None

# Banco de dados definitivo do histórico de quem já trabalhou e quando
if "historico_definitivo" not in st.session_state:
    st.session_state.historico_definitivo = pd.DataFrame(columns=["Grupo", "Tarefa", "Data de Trabalho", "Principal", "Ajudante"])

# --- FUNÇÃO DE LÓGICA PARA GERAR DUPLAS TOTALMENTE ALEATÓRIAS ---
def gerar_escala_sem_repeticao(membros):
    if len(membros) < 2:
        return None
    
    principais = membros.copy()
    random.shuffle(principais)
    
    ajudantes = membros.copy()
    
    # Busca uma combinação onde ninguém seja par de si mesmo
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
            "Data de Trabalho": datetime.today()
        })
        
    random.shuffle(escala)
    return pd.DataFrame(escala)

# --- INTERFACE DO USUÁRIO ---
st.title("👥 Sistema Gestão de Designações")
st.markdown("Gerencie seus grupos, edite datas de trabalho e mantenha o controle total do histórico.")

# Abas da Aplicação
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

        # Área Editável
        if st.session_state.escala_temporaria is not None:
            st.write("---")
            st.subheader("✍️ 2. Área Editável: Ajuste, Adicione ou Remova Duplas")
            
            st.markdown("""
            * **Editar:** Clique duplo na célula.
            * **Remover linha:** Selecione a linha na esquerda e aperte **Delete**.
            * **Adicionar linha:** Clique em **"➕ Add row"** no fim da tabela.
            """)
            
            escala_editada = st.data_editor(
                st.session_state.escala_temporaria,
                column_config={
                    "Principal": st.column_config.TextColumn("🧑‍✈️ Principal (Líder)", required=True),
                    "Ajudante": st.column_config.TextColumn("🧑‍🔧 Ajudante", required=True),
                    "Data de Trabalho": st.column_config.DateColumn(
                        "📅 Data de Trabalho",
                        min_value=datetime(2026, 1, 1),
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
                    
                    st.session_state.escala_temporaria = None
                    st.success("Sucesso! A sua escala personalizada foi salva no Histórico Consolidado.")
                    st.rerun()

# --- ABA 2: HISTÓRICO CONSOLIDADO ---
with aba_historico:
    st.header("📊 Histórico de Atividades Registradas")
    
    if not st.session_state.historico_definitivo.empty:
        df_exibir = st.session_state.historico_definitivo.sort_values(by="Data de Trabalho", ascending=False)
        st.dataframe(df_exibir, use_container_width=True, hide_index=True)
        
        csv = df_exibir.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar Histórico Completo (Excel/CSV)",
            data=csv,
            file_name="historico_geral_escalas.csv",
            mime='text/csv',
            use_container_width=True
        )
        
        st.write("")
        if st.button("🗑️ Limpar Todo o Histórico", use_container_width=True):
            st.session_state.historico_definitivo = pd.DataFrame(columns=["Grupo", "Tarefa", "Data de Trabalho", "Principal", "Ajudante"])
            st.rerun()
    else:
        st.info("Nenhum registro confirmado ainda. Monte uma escala na primeira aba e clique em 'Confirmar e Registrar'.")

# --- ABA 3: GESTÃO DE GRUPOS ---
with aba_grupos:
    st.header("🗂️ Gestão de Grupos e Integrantes")
    
    # ---------------------------------------------------------
    # SEÇÃO: ADICIONAR, RENOMEAR E REMOVER GRUPOS
    # ---------------------------------------------------------
    st.subheader("1. Gerenciar Grupos")
    col_add_grp, col_ren_grp, col_del_grp = st.columns(3)
    
    with col_add_grp:
        novo_grupo_nome = st.text_input("Criar Novo Grupo:", key="input_add_grp")
        if st.button("➕ Adicionar Grupo", use_container_width=True):
            if novo_grupo_nome.strip() == "":
                st.warning("Digite um nome válido.")
            elif novo_grupo_nome.strip() in st.session_state.grupos:
                st.warning("Esse grupo já existe.")
            else:
                st.session_state.grupos[novo_grupo_nome.strip()] = []
                st.success(f"Grupo '{novo_grupo_nome}' criado com sucesso!")
                st.rerun()
                
    with col_ren_grp:
        if st.session_state.grupos:
            grupo_a_renomear = st.selectbox("Grupo a Renomear:", list(st.session_state.grupos.keys()), key="select_ren_grp")
            novo_nome_para_grupo = st.text_input("Novo Nome:", key="input_ren_grp")
            if st.button("✏️ Confirmar Nome", use_container_width=True):
                if novo_nome_para_grupo.strip() == "":
                    st.warning("Digite um nome válido.")
                elif novo_nome_para_grupo.strip() in st.session_state.grupos:
                    st.warning("Já existe um grupo com este nome.")
                else:
                    st.session_state.grupos[novo_nome_para_grupo.strip()] = st.session_state.grupos.pop(grupo_a_renomear)
                    st.success("Grupo renomeado!")
                    st.rerun()

    with col_del_grp:
        if st.session_state.grupos:
            grupo_a_remover = st.selectbox("Excluir Grupo:", list(st.session_state.grupos.keys()), key="select_del_grp")
            if st.button("🗑️ Excluir Grupo", use_container_width=True):
                del st.session_state.grupos[grupo_a_remover]
                st.success("Grupo excluído com sucesso!")
                st.rerun()

    st.write("---")

    # ---------------------------------------------------------
    # SEÇÃO: GERENCIAR INTEGRANTES 
    # ---------------------------------------------------------
    st.subheader("2. Visualizar e Editar Integrantes")
    
    if not st.session_state.grupos:
        st.info("Não há grupos disponíveis. Crie um novo grupo acima.")
    else:
        # Visualização da tabela vinculada ao rádio (Apenas para visualização)
        grupo_visualizar = st.radio("Selecione o grupo para visualizar a lista de integrantes:", list(st.session_state.grupos.keys()), horizontal=True)
        lista_atual = st.session_state.grupos[grupo_visualizar]
        
        st.write(f"**Integrantes atuais do grupo '{grupo_visualizar}' ({len(lista_atual)} pessoas):**")
        st.dataframe(pd.DataFrame(lista_atual, columns=["Nome do Integrante"]), use_container_width=True, hide_index=True)
        
        st.write("---")
        col_adicionar, col_remover = st.columns([1, 1])
        
        with col_adicionar:
            st.markdown("#### ➕ Adicionar novo integrante em:")
            grupo_destino = st.selectbox("Escolha o grupo de destino:", list(st.session_state.grupos.keys()), key="select_add_destino")
            novo_nome = st.text_input("Digite o nome da pessoa para adicionar:", key="input_add_membro")
            
            if st.button("Confirmar Adição", type="secondary", use_container_width=True):
                if novo_nome.strip() == "":
                    st.warning("Por favor, digite um nome válido.")
                elif novo_nome.strip() in st.session_state.grupos[grupo_destino]:
                    st.warning(f"Esta pessoa já faz parte do grupo '{grupo_destino}'.")
                else:
                    st.session_state.grupos[grupo_destino].append(novo_nome.strip())
                    st.success(f"**{novo_nome.strip()}** foi adicionado(a) ao grupo **{grupo_destino}** com sucesso!")
                    st.rerun()
                    
        with col_remover:
            st.markdown("#### 🗑️ Remover do Grupo:")
            grupo_origem_remocao = st.selectbox("Escolha o grupo:", list(st.session_state.grupos.keys()), key="select_del_destino")
            lista_para_remocao = st.session_state.grupos[grupo_origem_remocao]
            
            if len(lista_para_remocao) > 0:
                # Checkbox para selecionar todos
                selecionar_todos = st.checkbox("Selecionar todos os integrantes", key="chk_sel_all")
                selecao_padrao = lista_para_remocao if selecionar_todos else []
                
                nomes_para_remover = st.multiselect(
                    "Selecione as pessoas que deseja remover:", 
                    options=lista_para_remocao, 
                    default=selecao_padrao,
                    key="select_remove_membro"
                )
                
                if st.button("Confirmar Remoção", type="primary", use_container_width=True):
                    if nomes_para_remover:
                        for nome in nomes_para_remover:
                            st.session_state.grupos[grupo_origem_remocao].remove(nome)
                        st.success(f"**{len(nomes_para_remover)}** integrante(s) removido(s) do grupo '{grupo_origem_remocao}'!")
                        st.rerun()
                    else:
                        st.warning("Por favor, selecione pelo menos um nome para remover.")
            else:
                st.info(f"O grupo '{grupo_origem_remocao}' está vazio.")

# --- RODAPÉ DA PÁGINA RESPONSIVO ---
st.write("---")
st.markdown(
    """
    <div style="text-align: center; color: #888888; font-size: 12px; padding: 10px 0px; width: 100%;">
        Criado, e atualizado por: Sérgio Sierra
    </div>
    """, 
    unsafe_allow_html=True
)