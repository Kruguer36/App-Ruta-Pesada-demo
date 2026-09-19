import json
import time
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

# Inicialización de estado
if "puntos_opcionales" not in st.session_state:
    st.session_state.puntos_opcionales = []
if "rutas_calculadas" not in st.session_state:
    st.session_state.rutas_calculadas = []
if "ruta_activa_idx" not in st.session_state:
    st.session_state.ruta_activa_idx = 0
if "paso_actual" not in st.session_state:
    st.session_state.paso_actual = 0
if "simulando" not in st.session_state:
    st.session_state.simulando = False

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

# Menú lateral
st.sidebar.title("🚚 RutaCarga Colombia")
modulo = st.sidebar.radio("Módulo:", ["1. Navegador GPS", "2. Programador", "3. Reportes"])

if modulo == "1. Navegador GPS":
    st.header("🧭 Navegador GPS Colombia (Demostración de Navegación)")

    # ESTRUCTURA EN PARALELO
    col_izquierda, col_derecha = st.columns([1, 1.2], gap="large")

    with col_izquierda:
        st.subheader("📋 Configuración y Controles del Demo")
        
        vehiculo = st.selectbox("🚚 Tipo de Vehículo", ["Carro", "Turbo", "Camión", "Tractomula"])
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
                    st.session_state.paso_actual = 0
                    st.session_state.simulando = False
                    st.rerun()

        # CONTROLES DE REPRODUCCIÓN AUTOMÁTICA EN EL DEMO
        if st.session_state.rutas_calculadas:
            st.markdown("---")
            st.subheader("▶️ Botones de Navegación")
            
            ruta_activa = st.session_state.rutas_calculadas[st.session_state.ruta_activa_idx]
            coords = ruta_activa["geometria"]

            st.info(f"Distancia: {ruta_activa['distancia']:.1f} km | Tiempo: {ruta_activa['tiempo']/60:.1f} hrs")

            col_b1, col_b2, col_b3 = st.columns(3)
            if col_b1.button("▶️ Iniciar", use_container_width=True):
                st.session_state.simulando = True
            if col_b2.button("⏸️ Pausar", use_container_width=True):
                st.session_state.simulando = False
            if col_b3.button("🔄 Reiniciar", use_container_width=True):
                st.session_state.paso_actual = 0
                st.session_state.simulando = False

            st.markdown("---")
            velocidad = st.slider("⚡ Velocidad de Simulación", min_value=1, max_value=10, value=3)

            if st.button("🧹 Limpiar Tablero Completo", use_container_width=True):
                st.session_state.puntos_opcionales.clear()
                st.session_state.rutas_calculadas.clear()
                st.session_state.paso_actual = 0
                st.session_state.simulando = False
                st.rerun()

    with col_derecha:
        st.subheader("🗺️ Vista en Vivo del Vehículo")
        
        # Contenedor dinámico que evita parpadeos y congelamientos
        mapa_placeholder = st.empty()
        
        def renderizar_mapa(paso_idx):
            ruta_activa = st.session_state.rutas_calculadas[st.session_state.ruta_activa_idx]
            coords = ruta_activa["geometria"]
            pos_actual = coords[paso_idx]

            idx_instr = min(int((paso_idx / len(coords)) * len(ruta_activa["instrucciones"])), len(ruta_activa["instrucciones"]) - 1)
            
            # Capa de la trayectoria en rojo
            capa_ruta = pdk.Layer(
                "PathLayer",
                data=[{"path": coords}],
                get_path="path",
                get_color=[255, 0, 0, 200],
                width_min_pixels=5,
            )

            # Capa del marcador del vehículo en color amarillo brillante resaltado
            df_cursor = pd.DataFrame([{"lon": pos_actual[0], "lat": pos_actual[1]}])
            capa_cursor = pdk.Layer(
                "ScatterplotLayer",
                data=df_cursor,
                get_position=["lon", "lat"],
                get_color=[255, 215, 0, 255],
                get_radius=120,
                radius_min_pixels=14,
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

            with mapa_placeholder.container():
                st.warning(f"📍 Estado: {ruta_activa['instrucciones'][idx_instr]} (Paso {paso_idx + 1} de {len(coords)})")
                st.pydeck_chart(pdk.Deck(layers=[capa_ruta, capa_cursor], initial_view_state=view_state))

        if st.session_state.rutas_calculadas:
            renderizar_mapa(st.session_state.paso_actual)
            
            # Ejecución fluida de la animación cuando presiones "Iniciar"
            if st.session_state.simulando:
                ruta_activa = st.session_state.rutas_calculadas[st.session_state.ruta_activa_idx]
                coords = ruta_activa["geometria"]
                
                while st.session_state.paso_actual < len(coords) - 1 and st.session_state.simulando:
                    st.session_state.paso_actual += velocidad
                    if st.session_state.paso_actual >= len(coords):
                        st.session_state.paso_actual = len(coords) - 1
                        st.session_state.simulando = False
                    
                    renderizar_mapa(st.session_state.paso_actual)
                    time.sleep(0.05)
        else:
            view_state_def = pdk.ViewState(longitude=-74.1, latitude=4.6, zoom=5)
            mapa_placeholder.pydeck_chart(pdk.Deck(initial_view_state=view_state_def))