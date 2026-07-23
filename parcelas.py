import os
import zipfile
import base64
import pandas as pd
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from github import Github, GithubException

# -----------------------------------------------------------------------------
# CONFIGURACIÓN PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Gestor Campo Escuela (Editor)",
    page_icon="🚜",
    layout="wide"
)

st.title("🚜 Editor de Parcelas - Campo Escuela")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# CONEXIÓN CON GITHUB API
# -----------------------------------------------------------------------------
def get_github_repo():
    """Obtiene la instancia del repositorio mediante el Token de Secrets."""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["GITHUB_REPO"]
        g = Github(token)
        return g.get_repo(repo_name)
    except Exception as e:
        st.error(f"Error al conectar con la API de GitHub: {e}")
        return None

def upload_to_github(file_bytes, filename):
    """Sube o actualiza un archivo en la carpeta data/ del repositorio en GitHub."""
    repo = get_github_repo()
    if not repo:
        return False

    path_in_repo = f"data/{filename}"
    commit_message = f"Add new parcel: {filename} via Streamlit Editor"

    try:
        # Si el archivo ya existe en GitHub, lo actualizamos pasándole el SHA
        contents = repo.get_contents(path_in_repo)
        repo.update_file(path_in_repo, commit_message, file_bytes, contents.sha)
    except GithubException as e:
        if e.status == 404:
            # Si no existe, lo creamos
            repo.create_file(path_in_repo, commit_message, file_bytes)
        else:
            st.error(f"Error al subir a GitHub: {e}")
            return False

    return True

def delete_from_github(filename):
    """Elimina un archivo de la carpeta data/ del repositorio en GitHub."""
    repo = get_github_repo()
    if not repo:
        return False

    path_in_repo = f"data/{filename}"
    commit_message = f"Delete parcel: {filename} via Streamlit Editor"

    try:
        contents = repo.get_contents(path_in_repo)
        repo.delete_file(path_in_repo, commit_message, contents.sha)
        return True
    except Exception as e:
        st.error(f"Error al eliminar de GitHub: {e}")
        return False


# -----------------------------------------------------------------------------
# LECTURA DE DATOS KML / KMZ
# -----------------------------------------------------------------------------
def load_spatial_data(file_source) -> gpd.GeoDataFrame:
    try:
        filename = file_source
        ext = os.path.splitext(filename)[1].lower()

        if ext == ".kml":
            gdf = gpd.read_file(file_source, driver="KML")
        elif ext == ".kmz":
            with zipfile.ZipFile(file_source, "r") as z:
                kml_filename = [f for f in z.namelist() if f.endswith(".kml")][0]
                with z.open(kml_filename) as kml_file:
                    gdf = gpd.read_file(kml_file, driver="KML")
        else:
            return gpd.GeoDataFrame()

        return gdf
    except Exception as e:
        st.error(f"Error al leer `{file_source}`: {e}")
        return gpd.GeoDataFrame()


# -----------------------------------------------------------------------------
# LOGIN SENCILLO
# -----------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.subheader("🔑 Iniciar Sesión para Editar")
    password = st.text_input("Contraseña de administrador:", type="password")
    if st.button("Ingresar"):
        # Podés cambiar esta clave o usar st.secrets["ADMIN_PASSWORD"]
        if password == "agro2026":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    st.stop()


# -----------------------------------------------------------------------------
# PANEL LATERAL: SUBIR PARCELA
# -----------------------------------------------------------------------------
st.sidebar.title("🛠️ Panel de Gestión")
uploaded_file = st.sidebar.file_uploader(
    "Cargar nueva parcela (KML / KMZ)", 
    type=["kml", "kmz"]
)

if uploaded_file is not None:
    filename = uploaded_file.name
    file_bytes = uploaded_file.getvalue()
    
    # 1. Guardar copia local temporal
    local_path = os.path.join(DATA_DIR, filename)
    with open(local_path, "wb") as f:
        f.write(file_bytes)
        
    if st.sidebar.button("💾 Guardar Parcela en GitHub"):
        with st.spinner("Subiendo parcela al repositorio de GitHub..."):
            success = upload_to_github(file_bytes, filename)
            if success:
                st.sidebar.success(f"¡{filename} guardado con éxito en GitHub!")
                st.rerun()

# -----------------------------------------------------------------------------
# LECTURA Y VISUALIZACIÓN DE CAPAS
# -----------------------------------------------------------------------------
spatial_files = []
if os.path.exists(DATA_DIR):
    spatial_files = [
        f for f in os.listdir(DATA_DIR) 
        if f.lower().endswith(".kml") or f.lower().endswith(".kmz")
    ]

base_files = [f for f in spatial_files if "campo" in f.lower() or "lote" in f.lower()]
uploaded_files = [f for f in spatial_files if f not in base_files]
ordered_files = base_files + uploaded_files

m = folium.Map(location=[-31.42, -64.18], zoom_start=13, tiles="OpenStreetMap")
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", name="Google Satélite").add_to(m)

gdfs_to_bounds = []

if ordered_files:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Capas visibles:")
    
    for file_name in ordered_files:
        file_path = os.path.join(DATA_DIR, file_name)
        is_base = file_name in base_files
        
        show_layer = st.sidebar.checkbox(
            f"{'📍 Base: ' if is_base else '🔹 '} {file_name}", 
            value=True
        )
        
        if show_layer:
            gdf = load_spatial_data(file_path)
            if not gdf.empty:
                gdfs_to_bounds.append(gdf)
                style_color = "#28a745" if is_base else "#ff3333"
                
                folium.GeoJson(
                    gdf,
                    name=file_name,
                    style_function=lambda x, color=style_color: {
                        'fillColor': color,
                        'color': color,
                        'weight': 2,
                        'fillOpacity': 0.4
                    }
                ).add_to(m)

if gdfs_to_bounds:
    combined_gdf = gpd.GeoDataFrame(pd.concat(gdfs_to_bounds, ignore_index=True))
    bounds = combined_gdf.total_bounds
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

folium.LayerControl().add_to(m)
st_folium(m, width="100%", height=500)


# -----------------------------------------------------------------------------
# SECCIÓN DE ELIMINACIÓN DE PARCELAS
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("🗑️ Administrar y Eliminar Parcelas Subidas")

if not uploaded_files:
    st.info("No hay parcelas adicionales para eliminar.")
else:
    for file_name in uploaded_files:
        col1, col2 = st.columns([4, 1])
        col1.text(f"🔹 Parcela: {file_name}")
        
        if col2.button("❌ Eliminar", key=f"del_{file_name}"):
            with st.spinner("Eliminando parcela de GitHub..."):
                # 1. Borrar de GitHub
                success = delete_from_github(file_name)
                
                # 2. Borrar copia local si existe
                local_path = os.path.join(DATA_DIR, file_name)
                if os.path.exists(local_path):
                    os.remove(local_path)
                
                if success:
                    st.success(f"Parcela `{file_name}` eliminada correctamente.")
                    st.rerun()
