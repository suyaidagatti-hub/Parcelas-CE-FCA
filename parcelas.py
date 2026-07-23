import os
import zipfile
import datetime
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
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["GITHUB_REPO"]
        g = Github(token)
        return g.get_repo(repo_name)
    except Exception as e:
        st.error(f"Error al conectar con la API de GitHub: {e}")
        return None

def upload_to_github(file_bytes, filename):
    repo = get_github_repo()
    if not repo:
        return False

    path_in_repo = f"data/{filename}"
    commit_message = f"Add new parcel: {filename} via Streamlit Editor"

    try:
        contents = repo.get_contents(path_in_repo)
        repo.update_file(path_in_repo, commit_message, file_bytes, contents.sha)
    except GithubException as e:
        if e.status == 404:
            repo.create_file(path_in_repo, commit_message, file_bytes)
        else:
            st.error(f"Error al subir a GitHub: {e}")
            return False

    return True

def delete_from_github(filename):
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
# LOGIN CON CREDENCIALES DESDE CSV
# -----------------------------------------------------------------------------
def verificar_credenciales(usuario, clave) -> bool:
    if not os.path.exists("credenciales.csv"):
        st.error("No se encontró el archivo `credenciales.csv` en la raíz del proyecto.")
        return False
    
    try:
        df_creds = pd.read_csv("credenciales.csv")
        match = df_creds[(df_creds['usuario'].astype(str) == usuario.strip()) & 
                         (df_creds['contraseña'].astype(str) == clave.strip())]
        return not match.empty
    except Exception as e:
        st.error(f"Error al leer credenciales.csv: {e}")
        return False


if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.subheader("🔑 Iniciar Sesión para Editar")
    col_usr, col_pwd = st.columns(2)
    with col_usr:
        user_input = st.text_input("Usuario:")
    with col_pwd:
        pass_input = st.text_input("Contraseña:", type="password")
        
    if st.button("Ingresar"):
        if verificar_credenciales(user_input, pass_input):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()


# -----------------------------------------------------------------------------
# LECTURA DE DATOS KML / KMZ
# -----------------------------------------------------------------------------
def load_spatial_data(file_source) -> gpd.GeoDataFrame:
    try:
        ext = os.path.splitext(file_source)[1].lower()

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
                fill_opacity = 0.25 if is_base else 0.55
                weight = 2 if is_base else 3

                # Selección de campos para el Tooltip (Pop-up al pasar el mouse)
                tooltip_fields = [c for c in gdf.columns if c.lower() != 'geometry']
                
                geojson_layer = folium.GeoJson(
                    gdf,
                    name=file_name,
                    style_function=lambda x, color=style_color, opacity=fill_opacity, w=weight: {
                        'fillColor': color,
                        'color': color,
                        'weight': w,
                        'fillOpacity': opacity
                    },
                    highlight_function=lambda x: {
                        'weight': 4,
                        'fillOpacity': 0.85
                    }
                )
                
                # Restaurar Pop-up/Tooltip al pasar el cursor
                if tooltip_fields:
                    geojson_layer.add_child(
                        folium.GeoJsonTooltip(
                            fields=tooltip_fields[:3],  # Muestra los primeros 3 atributos (Name, Description, etc.)
                            aliases=[f"{col}:" for col in tooltip_fields[:3]],
                            sticky=True
                        )
                    )
                
                geojson_layer.add_to(m)

if gdfs_to_bounds:
    combined_gdf = gpd.GeoDataFrame(pd.concat(gdfs_to_bounds, ignore_index=True))
    bounds = combined_gdf.total_bounds
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

folium.LayerControl().add_to(m)
st_folium(m, width="100%", height=500)


# -----------------------------------------------------------------------------
# SECCIÓN DE ADMINISTRACIÓN Y FECHA DE CARGA (RESTAURADA)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📋 Detalle de Parcelas Cargadas")

if not spatial_files:
    st.info("No hay capas cargadas en la carpeta de datos.")
else:
    col1, col2, col3, col4 = st.columns([4, 3, 3, 2])
    col1.markdown("**Nombre del Archivo**")
    col2.markdown("**Tipo de Capa**")
    col3.markdown("**Fecha de Carga / Modificación**")
    col4.markdown("**Acción**")
    st.markdown("---")

    for file_name in spatial_files:
        file_path = os.path.join(DATA_DIR, file_name)
        is_base = file_name in base_files
        
        # Obtener fecha de modificación del archivo
        mod_time = os.path.getmtime(file_path)
        fecha_carga = datetime.datetime.fromtimestamp(mod_time).strftime("%d/%m/%Y - %H:%M hs")
        
        c1, c2, c3, c4 = st.columns([4, 3, 3, 2])
        c1.text(f"📄 {file_name}")
        c2.caption("📍 Lote Base (Campo Escuela)" if is_base else "🔹 Parcela Integrada")
        c3.text(fecha_carga)
        
        if not is_base:
            if c4.button("❌ Eliminar", key=f"del_{file_name}"):
                with st.spinner("Eliminando parcela de GitHub..."):
                    success = delete_from_github(file_name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    if success:
                        st.success(f"Parcela `{file_name}` eliminada correctamente.")
                        st.rerun()
        else:
            c4.caption("🔒 Protegida")
