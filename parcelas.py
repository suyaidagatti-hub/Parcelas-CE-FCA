import os
import zipfile
import tempfile
import datetime
import pandas as pd
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
st.markdown("Visualización e integración de capas de lotes y parcelas en formato KML y KMZ.")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# FUNCIÓN PARA LEER KML / KMZ
# -----------------------------------------------------------------------------
def load_spatial_data(file_source) -> gpd.GeoDataFrame:
    """
    Lee archivos KML o KMZ y los convierte en un GeoDataFrame.
    """
    try:
        if hasattr(file_source, "name"):
            filename = file_source.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
                tmp.write(file_source.getvalue())
                tmp_path = tmp.name
        else:
            filename = file_source
            tmp_path = file_source

        ext = os.path.splitext(filename)[1].lower()

        if ext == ".kml":
            gdf = gpd.read_file(tmp_path, driver="KML")
        elif ext == ".kmz":
            with zipfile.ZipFile(tmp_path, "r") as z:
                kml_filename = [f for f in z.namelist() if f.endswith(".kml")][0]
                with z.open(kml_filename) as kml_file:
                    gdf = gpd.read_file(kml_file, driver="KML")
        else:
            return gpd.GeoDataFrame()

        if hasattr(file_source, "name") and os.path.exists(tmp_path):
            os.remove(tmp_path)

        return gdf

    except Exception as e:
        st.error(f"Error al leer `{getattr(file_source, 'name', file_source)}`: {e}")
        return gpd.GeoDataFrame()


# -----------------------------------------------------------------------------
# SIDEBAR: Carga de Nuevos Archivos
# -----------------------------------------------------------------------------
st.sidebar.header("📁 Cargar Nueva Parcela")
uploaded_file = st.sidebar.file_uploader("Sube un archivo KML o KMZ", type=["kml", "kmz"])

if uploaded_file is not None:
    save_path = os.path.join(DATA_DIR, uploaded_file.name)
    
    if not os.path.exists(save_path):
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.sidebar.success(f"Guardado exitosamente: `{uploaded_file.name}`")
        st.rerun()
    else:
        st.sidebar.info(f"El archivo `{uploaded_file.name}` ya existe en la base de datos.")


# -----------------------------------------------------------------------------
# GESTIÓN Y ORDENAMIENTO DE CAPAS
# -----------------------------------------------------------------------------
spatial_files = [
    f for f in os.listdir(DATA_DIR) 
    if f.lower().endswith(".kml") or f.lower().endswith(".kmz")
]

# Separar la capa base de los lotes del campo escuela de las parcelas cargadas
base_files = [f for f in spatial_files if "campo" in f.lower() or "lote" in f.lower()]
uploaded_files = [f for f in spatial_files if f not in base_files]

ordered_files = base_files + uploaded_files

# Mapa base
m = folium.Map(location=[-31.42, -64.18], zoom_start=13, tiles="OpenStreetMap")
folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", name="Google Satélite").add_to(m)

gdfs_to_bounds = []

if ordered_files:
    st.sidebar.subheader("🗂️ Visibilidad de Capas")
    
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
                
                if is_base:
                    style_color = "#28a745"  # Verde para base
                    fill_opacity = 0.25
                    weight = 2
                else:
                    style_color = "#ff3333"  # Rojo/Naranja para parcelas subidas
                    fill_opacity = 0.55
                    weight = 3

                folium.GeoJson(
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
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=list(gdf.columns.drop('geometry', errors='ignore'))[:3],
                        sticky=True
                    ) if len(gdf.columns) > 1 else None
                ).add_to(m)

# Centrar mapa automáticamente
if gdfs_to_bounds:
    combined_gdf = gpd.GeoDataFrame(pd.concat(gdfs_to_bounds, ignore_index=True))
    bounds = combined_gdf.total_bounds
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

folium.LayerControl().add_to(m)


# -----------------------------------------------------------------------------
# MOSTRAR MAPA
# -----------------------------------------------------------------------------
st_folium(m, width="100%", height=550)


# -----------------------------------------------------------------------------
# REGISTRO Y GESTIÓN DE PARCELAS (DEBAJO DEL MAPA)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📋 Registro de Parcelas Cargadas / Base de Datos")

if not spatial_files:
    st.info("No hay capas ni parcelas cargadas en la base de datos.")
else:
    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
    col1.markdown("**Nombre del Archivo**")
    col2.markdown("**Tipo de Capa**")
    col3.markdown("**Fecha de Carga**")
    col4.markdown("**Acción**")
    st.markdown("---")

    for file_name in spatial_files:
        file_path = os.path.join(DATA_DIR, file_name)
        is_base = file_name in base_files
        
        mod_time = os.path.getmtime(file_path)
        # Se formatea la fecha únicamente en día/mes/año (DD/MM/YYYY)
        fecha_carga = datetime.datetime.fromtimestamp(mod_time).strftime("%d/%m/%Y")
        
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        
        c1.text(f"📄 {file_name}")
        c2.caption("📍 Lote Base (Campo Escuela)" if is_base else "🔹 Parcela Añadida")
        c3.text(fecha_carga)
        
        # Protección de borrado para capa base
        if is_base:
            c4.caption("🔒 Protegido")
        else:
            if c4.button("🗑️ Borrar", key=f"del_{file_name}"):
                try:
                    os.remove(file_path)
                    st.toast(f"Se eliminó `{file_name}` correctamente.", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al borrar el archivo: {e}")
