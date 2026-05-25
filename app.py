import streamlit as st
import pandas as pd
import random
from datetime import datetime

# Configuração inicial da página web - layout wide adapta-se dinamicamente ao container do navegador
st.set_page_config(page_title="Gestão de Pessoas e Tarefas", layout="wide", initial_sidebar_state="collapsed")

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
st.title("👥 Sistema de Gestão de Pessoas e Escala de Tarefas")
st.markdown("Gerencie seus grupos, edite datas de trabalho e mantenha o controle total do histórico.")

# Abas da Aplicação - O Streamlit converte automaticamente em menu colapsável ou rolável em telas mobile
aba_gerador, aba_historico, aba_grupos = st.tabs(["🗓️ Gerar e Editar Escala", "📊 Histórico Consolidado", "🗂️ Gestão de Grupos"])

# --- ABA 1: GERAR E EDITAR ESCALA ---
with aba_gerador:
    st.header("1. Configurar Nova Atividade")
    
    # col1 e col2 se adaptam ao tamanho do dispositivo (lado a lado no PC, empilhados no celular)
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
        
        # O data_editor herda a largura total do dispositivo (computador ou mobile)
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
        
        # Botões expandem para ocupar a largura total em telas de celular
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
    st.header("🗂️ Visualizar e Editar Integrantes")
    grupo_visualizar = st.radio("Selecione o grupo para gerenciar:", list(st.session_state.grupos.keys()), horizontal=True)
    lista_atual = st.session_state.grupos[grupo_visualizar]
    
    st.write(f"**Integrantes atuais ({len(lista_atual)} pessoas):**")
    st.dataframe(pd.DataFrame(lista_atual, columns=["Nome do Integrante"]), use_container_width=True, hide_index=True)
    
    st.write("---")
    
    # Colunas responsivas para os formulários de adição e remoção
    col_adicionar, col_remover = st.columns([1, 1])
    
    with col_adicionar:
        st.subheader("➕ Adicionar Integrante")
        novo_nome = st.text_input("Digite o nome da pessoa para adicionar:", key="input_add")
        if st.button("Confirmar Adição", type="secondary", use_container_width=True):
            if novo_nome.strip() == "":
                st.warning("Por favor, digite um nome válido.")
            elif novo_nome.strip() in lista_atual:
                st.warning("Esta pessoa já faz parte deste grupo.")
            else:
                st.session_state.grupos[grupo_visualizar].append(novo_nome.strip())
                st.success(f"**{novo_nome.strip()}** foi adicionado(a) com sucesso!")
                st.rerun()
                
    with col_remover:
        st.subheader("🗑️ Remover Integrante")
        if len(lista_atual) > 0:
            nome_para_remover = st.selectbox("Selecione a pessoa que deseja remover:", lista_atual, key="select_remove")
            if st.button("Confirmar Remoção", type="primary", use_container_width=True):
                st.session_state.grupos[grupo_visualizar].remove(nome_para_remover)
                st.success(f"**{nome_para_remover}** foi removido(a) do grupo!")
                st.rerun()
        else:
            st.info("Não há integrantes neste grupo para remover.")

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