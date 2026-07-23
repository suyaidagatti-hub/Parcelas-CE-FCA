import os
import zipfile
import tempfile
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tablero GIS - Campo Escuela",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 Visualizador de Parcelas - Campo Escuela")
st.markdown("Visualización e integración de capas de lotes y parcelas en formato KMZ.")

# Directorio donde se guardará la base de datos de archivos KMZ
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# FUNCIONES AUXILIARES DE GIS
# -----------------------------------------------------------------------------
def read_kmz(kmz_source) -> gpd.GeoDataFrame:
    """
    Descomprime en memoria o archivo temporal un KMZ para extraer 
    el KML interno y devolver un GeoDataFrame.
    """
    try:
        # Si es un objeto cargado desde st.file_uploader
        if hasattr(kmz_source, "read"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".kmz") as tmp:
                tmp.write(kmz_source.getvalue())
                tmp_path = tmp.name
        else:
            tmp_path = kmz_source

        # Descomprimir el archivo KML del KMZ
        with zipfile.ZipFile(tmp_path, "r") as z:
            kml_filename = [f for f in z.namelist() if f.endswith(".kml")][0]
            with z.open(kml_filename) as kml_file:
                # Activar el driver de KML en fiona/pyogrio a través de geopandas
                gdf = gpd.read_file(kml_file, driver="KML")
        
        # Eliminar temporal si se creó uno
        if hasattr(kmz_source, "read") and os.path.exists(tmp_path):
            os.remove(tmp_path)

        return gdf
    except Exception as e:
        st.error(f"Error al procesar el archivo KMZ: {e}")
        return gpd.GeoDataFrame()


# -----------------------------------------------------------------------------
# SIDEBAR: Carga de Nuevos KMZ
# -----------------------------------------------------------------------------
st.sidebar.header("📁 Cargar Nueva Parcela")
uploaded_file = st.sidebar.file_uploader("Sube un archivo KMZ", type=["kmz"])

if uploaded_file is not None:
    save_path = os.path.join(DATA_DIR, uploaded_file.name)
    
    # Guardar en la 'base de datos' local del repo si no existe
    if not os.path.exists(save_path):
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.sidebar.success(f"Guardado exitosamente: `{uploaded_file.name}`")
    else:
        st.sidebar.info(f"El archivo `{uploaded_file.name}` ya existía en la base de datos.")


# -----------------------------------------------------------------------------
# LECTURA DE CAPAS
# -----------------------------------------------------------------------------
# Listar todos los archivos KMZ en el directorio 'data'
all_kmz_files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(".kmz")]

# Inicializar mapa centrado por defecto en Córdoba (Campo Escuela)
m = folium.Map(location=[-31.42, -64.18], zoom_start=13, tiles="OpenStreetMap")
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", name="Google Satélite").add_to(m)

gdfs_to_bounds = []

if all_kmz_files:
    st.sidebar.subheader("🗂️ Capas Disponibles")
    
    for file_name in all_kmz_files:
        file_path = os.path.join(DATA_DIR, file_name)
        is_base = "campo_escuela" in file_name.lower() or file_name == "lotes_campo_escuela.kmz"
        
        # Permite activar/desactivar la visualización de capas en el sidebar
        show_layer = st.sidebar.checkbox(
            f"{'📍 Base: ' if is_base else '🔹 '} {file_name}", 
            value=True
        )
        
        if show_layer:
            gdf = read_kmz(file_path)
            if not gdf.empty:
                gdfs_to_bounds.append(gdf)
                
                # Definir colores opcionales
                style_color = "#3388ff" if is_base else "#ff7800"
                
                # Agregar capa GeoJSON al mapa de Folium
                folium.GeoJson(
                    gdf,
                    name=file_name,
                    style_function=lambda x, color=style_color: {
                        'fillColor': color,
                        'color': color,
                        'weight': 2,
                        'fillOpacity': 0.3
                    },
                    tooltip=folium.GeoJsonTooltip(fields=list(gdf.columns.drop('geometry', errors='ignore'))[:3])
                ).add_to(m)

# Centrar el mapa automáticamente en el bounding box de todas las capas activas
if gdfs_to_bounds:
    combined_bounds = gpd.GeoDataFrame(pd.concat(gdfs_to_bounds, ignore_index=True)).total_bounds
    # total_bounds devuelve [minx, miny, maxx, maxy] -> Folium fit_bounds prefiere [[miny, minx], [maxy, maxx]]
    m.fit_bounds([[combined_bounds[1], combined_bounds[0]], [combined_bounds[3], combined_bounds[2]]])

folium.LayerControl().add_to(m)

# -----------------------------------------------------------------------------
# MOSTRAR MAPA
# -----------------------------------------------------------------------------
st_folium(m, width="100%", height=600)
