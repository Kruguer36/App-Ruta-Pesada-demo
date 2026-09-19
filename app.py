import json
import urllib.parse
import urllib.request
import pandas as pd
import pydeck as pdk
import streamlit as st

st.set_page_config(
    page_title="RutaCarga Colombia - Navegador GPS",
    page_icon="🚚",
    layout="wide"
)

# Inicialización de estados
if "puntos_opcionales" not in st.session_state:
    st.session_state.puntos_opcionales = []
if "rutas_calculadas" not in st.session_state:
    st.session_state.rutas_calculadas = []
if "ruta_activa_idx" not in st.session_state:
    st.session_state.ruta_activa_idx = 0

def normalizar_texto(texto):
    reemplazos = {"cra": "Carrera", "cll": "Calle", "av": "Avenida"}
    palabras = [reemplazos.get(p.lower().replace(".", ""), p) for p in texto.split()]
    return " ".join(palabras)

def buscar_lugar_colombia(busqueda):
    texto_limpio = normalizar_texto(busqueda)
    query = urllib.parse.quote(f"{texto_limpio}, Colombia")
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}&viewbox=-79.0,13.0,-66.0,-4.0&bounded=1"
    req = urllib.request.Request(url, headers={'User-Agent': 'RutaCarga_Colombia_App'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if data:
                return [float(data[0]['lon']), float(data[0]['lat'])]
    except Exception:
        pass
    return None

def calcular_rutas_osrm(pt_a, pt_b, intermedios):
    puntos_totales = [pt_a] + [p["point"] for p in intermedios] + [pt_b]
    coords_str = ";".join([f"{p[0]},{p[1]}" for p in puntos_totales])
    url_osrm = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson&steps=true&alternatives=true"
    
    req = urllib.request.Request(url_osrm, headers={'User-Agent': 'RutaCarga_Colombia_App'})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            if data.get("code") == "Ok":
                rutas = []
                for idx, r in enumerate(data["routes"][:2]):
                    coords = r["geometry"]["coordinates"]
                    dist_km = r["distance"] / 1000.0
                    dur_min = r["duration"] / 60.0
                    instrucciones = []
                    for leg in r["legs"]:
                        for step in leg["steps"]:
                            calle = step.get("name") or "Vía Nacional / Troncal"
                            instrucciones.append(f"Vía: {calle}")
                    rutas.append({
                        "geometria": coords,
                        "distancia": dist_km,
                        "tiempo": dur_min,
                        "instrucciones": instrucciones,
                        "nombre": f"Ruta {idx+1} ({'Principal' if idx==0 else 'Alternativa'})"
                    })
                return rutas
    except Exception:
        pass
    return []

# Sidebar
st.sidebar.title("🚚 RutaCarga Colombia")
modulo = st.sidebar.radio("Módulo:", ["1. Navegador GPS", "2. Programador", "3. Reportes"])

if modulo == "1. Navegador GPS":
    st.header("🧭 Navegador GPS Colombia")

    # DISTRIBUCIÓN EN PARALELO (COLUMNA IZQUIERDA Y DERECHA)
    col_izquierda, col_derecha = st.columns([1, 1.2], gap="large")

    with col_izquierda:
        st.subheader("📋 Configuración y Controles")
        
        vehiculo = st.selectbox("🚚 Vehículo", ["Carro", "Turbo", "Camión", "Tractomula"])
        input_a = st.text_input("🟢 Origen (Punto A)", value="Envigado, Antioquia")
        input_b = st.text_input("🔴 Destino (Punto B)", value="Bogota, Cundinamarca")
        
        input_opcional = st.text_input("🟡 Parada Intermedia (Opcional)", value="Manizales, Caldas")
        c1, c2 = st.columns(2)
        if c1.button("➕ Añadir Parada"):
            if input_opcional.strip():
                pt = buscar_lugar_colombia(input_opcional)
                if pt:
                    st.session_state.puntos_opcionales.append({"nombre": input_opcional, "point": pt})
                    st.success("Parada agregada")
        if c2.button("🗑️ Limpiar Paradas"):
            st.session_state.puntos_opcionales.clear()

        if st.button("🚀 Calcular Ruta Nacional", type="primary", use_container_width=True):
            pt_a = buscar_lugar_colombia(input_a)
            pt_b = buscar_lugar_colombia(input_b)
            if pt_a and pt_b:
                rutas = calcular_rutas_osrm(pt_a, pt_b, st.session_state.puntos_opcionales)
                if rutas:
                    st.session_state.rutas_calculadas = rutas
                    st.session_state.ruta_activa_idx = 0
                    st.rerun()

        # CONTROLES Y LIMPIEZA EN PARALELO
        if st.session_state.rutas_calculadas:
            st.markdown("---")
            st.subheader("🎛️ Controles de Simulación")
            
            ruta_activa = st.session_state.rutas_calculadas[st.session_state.ruta_activa_idx]
            coords = ruta_activa["geometria"]

            st.info(f"Distancia: {ruta_activa['distancia']:.1f} km | Tiempo: {ruta_activa['tiempo']/60:.1f} hrs")

            # Deslizador suave para evitar congelamientos de pantalla
            paso = st.slider(
                "📍 Posición del Vehículo a lo largo de la ruta",
                min_value=0,
                max_value=len(coords) - 1,
                value=0,
                step=1
            )
            
            if st.button("🧹 Limpiar Todo el Tablero", use_container_width=True):
                st.session_state.puntos_opcionales.clear()
                st.session_state.rutas_calculadas.clear()
                st.rerun()

    with col_derecha:
        st.subheader("🗺️ Vista de Mapa y Rastreo")
        
        if st.session_state.rutas_calculadas:
            ruta_activa = st.session_state.rutas_calculadas[st.session_state.ruta_activa_idx]
            coords = ruta_activa["geometria"]
            pos_actual = coords[paso]

            # Indicador de estado del punto
            idx_instr = min(int((paso / len(coords)) * len(ruta_activa["instrucciones"])), len(ruta_activa["instrucciones"]) - 1)
            st.warning(f"📍 Posición actual: {ruta_activa['instrucciones'][idx_instr]}")

            # Capas del mapa
            capa_ruta = pdk.Layer(
                "PathLayer",
                data=[{"path": coords}],
                get_path="path",
                get_color=[255, 0, 0, 200],
                width_min_pixels=5,
            )

            # Capa del vehículo (Círculo rojo brillante resaltado)
            df_cursor = pd.DataFrame([{"lon": pos_actual[0], "lat": pos_actual[1]}])
            capa_cursor = pdk.Layer(
                "ScatterplotLayer",
                data=df_cursor,
                get_position=["lon", "lat"],
                get_color=[255, 215, 0, 255], # Color dorado brillante
                get_radius=80,
                radius_min_pixels=12,
                stroked=True,
                get_line_color=[0, 0, 0, 255],
                line_width_min_pixels=3
            )

            view_state = pdk.ViewState(
                longitude=pos_actual[0],
                latitude=pos_actual[1],
                zoom=11,
                pitch=30
            )

            st.pydeck_chart(pdk.Deck(layers=[capa_ruta, capa_cursor], initial_view_state=view_state))
        else:
            view_state_def = pdk.ViewState(longitude=-74.1, latitude=4.6, zoom=5)
            st.pydeck_chart(pdk.Deck(initial_view_state=view_state_def))