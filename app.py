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

# --- INICIALIZACIÓN DE ESTADOS GLOBALES ---
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
if "despachos" not in st.session_state:
    st.session_state.despachos = [
        {"id": "DSP-001", "origen": "Medellín", "destino": "Bogotá", "vehiculo": "Tractomula", "conductor": "Carlos Pérez", "fecha": "2026-09-20", "hora": "06:00", "estado": "Programado"},
        {"id": "DSP-002", "origen": "Cali", "destino": "Buenaventura", "vehiculo": "Turbo", "conductor": "Martha Gómez", "fecha": "2026-09-21", "hora": "08:30", "estado": "En Tránsito"}
    ]

# --- FUNCIONES AUXILIARES DE RUTAS Y GEOCODIFICACIÓN ---
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
                        "nombre": f"Ruta {idx+1} ({'Principal' if idx==0 else 'Alternativa 2da Opción'})"
                    })
                return rutas
    except Exception:
        pass
    return []

# --- BARRA LATERAL (MENÚ Y PERSONALIZACIÓN DE MAPA) ---
st.sidebar.title("🚚 RutaCarga Colombia")
modulo = st.sidebar.radio("Seleccione Módulo:", ["1. Navegador GPS", "2. Programador", "3. Reportes"])

st.sidebar.markdown("---")
st.sidebar.subheader("🎨 Estilo de Mapa")
map_style_option = st.sidebar.selectbox(
    "Fondo del Mapa:",
    ["Oscuro (Dark)", "Claro (Light)", "Callejero (Roads)", "Exteriores (Outdoors)"]
)

# Cadenas de texto compatibles con PyDeck
map_styles = {
    "Oscuro (Dark)": "dark",
    "Claro (Light)": "light",
    "Callejero (Roads)": "road",
    "Exteriores (Outdoors)": "outdoors"
}
estilo_mapa_seleccionado = map_styles[map_style_option]


# ==============================================================================
# MÓDULO 1: NAVEGADOR GPS
# ==============================================================================
if modulo == "1. Navegador GPS":
    st.header("🧭 Navegador GPS Colombia")

    col_izquierda, col_derecha = st.columns([1, 1.2], gap="large")

    with col_izquierda:
        st.subheader("📋 Configuración y Controles")
        
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

        # SELECCIÓN DE RUTA ALTERNA Y CONTROLES
        if st.session_state.rutas_calculadas:
            st.markdown("---")
            st.subheader("🔀 Rutas Encontradas")
            
            nombres_rutas = [r["nombre"] for r in st.session_state.rutas_calculadas]
            idx_seleccionado = st.radio(
                "Seleccione la ruta a seguir:",
                range(len(nombres_rutas)),
                format_func=lambda x: nombres_rutas[x]
            )
            if idx_seleccionado != st.session_state.ruta_activa_idx:
                st.session_state.ruta_activa_idx = idx_seleccionado
                st.session_state.paso_actual = 0
                st.session_state.simulando = False

            ruta_activa = st.session_state.rutas_calculadas[st.session_state.ruta_activa_idx]
            st.info(f"**Distancia:** {ruta_activa['distancia']:.1f} km | **Tiempo:** {ruta_activa['tiempo']/60:.1f} hrs")

            st.markdown("---")
            st.subheader("▶️ Botones de Navegación")

            col_b1, col_b2, col_b3 = st.columns(3)
            if col_b1.button("▶️ Iniciar", use_container_width=True):
                st.session_state.simulando = True
            if col_b2.button("⏸️ Pausar", use_container_width=True):
                st.session_state.simulando = False
            if col_b3.button("🔄 Reiniciar", use_container_width=True):
                st.session_state.paso_actual = 0
                st.session_state.simulando = False

            velocidad = st.slider("⚡ Velocidad de Simulación", min_value=1, max_value=10, value=3)

            if st.button("🧹 Limpiar Tablero Completo", use_container_width=True):
                st.session_state.puntos_opcionales.clear()
                st.session_state.rutas_calculadas.clear()
                st.session_state.paso_actual = 0
                st.session_state.simulando = False
                st.rerun()

    with col_derecha:
        st.subheader("🗺️ Vista en Vivo del Vehículo")
        mapa_placeholder = st.empty()
        
        def renderizar_mapa(paso_idx):
            layers = []
            
            # Trazar rutas calculadas
            for i, r in enumerate(st.session_state.rutas_calculadas):
                es_activa = (i == st.session_state.ruta_activa_idx)
                layers.append(
                    pdk.Layer(
                        "PathLayer",
                        data=[{"path": r["geometria"]}],
                        get_path="path",
                        get_color=[255, 0, 0, 220] if es_activa else [100, 150, 200, 160],
                        width_min_pixels=6 if es_activa else 3,
                    )
                )

            ruta_activa = st.session_state.rutas_calculadas[st.session_state.ruta_activa_idx]
            coords = ruta_activa["geometria"]
            pos_actual = coords[paso_idx]

            idx_instr = min(int((paso_idx / len(coords)) * len(ruta_activa["instrucciones"])), len(ruta_activa["instrucciones"]) - 1)
            
            # Marcador del vehículo
            df_cursor = pd.DataFrame([{"lon": pos_actual[0], "lat": pos_actual[1]}])
            layers.append(
                pdk.Layer(
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
            )

            view_state = pdk.ViewState(
                longitude=pos_actual[0],
                latitude=pos_actual[1],
                zoom=11,
                pitch=30
            )

            with mapa_placeholder.container():
                st.warning(f"📍 Estado ({ruta_activa['nombre']}): {ruta_activa['instrucciones'][idx_instr]}")
                st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state, map_style=estilo_mapa_seleccionado))

        if st.session_state.rutas_calculadas:
            renderizar_mapa(st.session_state.paso_actual)
            
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
            mapa_placeholder.pydeck_chart(pdk.Deck(initial_view_state=view_state_def, map_style=estilo_mapa_seleccionado))


# ==============================================================================
# MÓDULO 2: PROGRAMADOR
# ==============================================================================
elif modulo == "2. Programador":
    st.header("📅 Programador de Despachos y Rutas")
    
    col_p1, col_p2 = st.columns([1, 1.5], gap="large")
    
    with col_p1:
        st.subheader("📝 Agendar Nuevo Despacho")
        p_origen = st.text_input("Ciudad de Origen", value="Medellín")
        p_destino = st.text_input("Ciudad de Destino", value="Cartagena")
        p_vehiculo = st.selectbox("Tipo de Vehículo", ["Tractomula", "Camión", "Turbo", "Carro"])
        p_conductor = st.selectbox("Asignar Conductor", ["Carlos Pérez", "Martha Gómez", "Juan Rodríguez", "Andrés López"])
        p_fecha = st.date_input("Fecha de Salida")
        p_hora = st.time_input("Hora de Salida")
        
        if st.button("➕ Agendar Despacho", type="primary", use_container_width=True):
            nuevo_id = f"DSP-00{len(st.session_state.despachos) + 1}"
            st.session_state.despachos.append({
                "id": nuevo_id,
                "origen": p_origen,
                "destino": p_destino,
                "vehiculo": p_vehiculo,
                "conductor": p_conductor,
                "fecha": str(p_fecha),
                "hora": str(p_hora),
                "estado": "Programado"
            })
            st.success(f"Despacho {nuevo_id} agendado correctamente.")

    with col_p2:
        st.subheader("📋 Lista de Despachos Agendados")
        df_despachos = pd.DataFrame(st.session_state.despachos)
        st.dataframe(df_despachos, use_container_width=True)


# ==============================================================================
# MÓDULO 3: REPORTES
# ==============================================================================
elif modulo == "3. Reportes":
    st.header("📊 Reportes Operativos y Métricas")
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Viajes Realizados", "142", "+12%")
    kpi2.metric("Distancia Recorrida", "38,450 km", "+8%")
    kpi3.metric("Consumo Combustible", "3,845 Gal", "-3%")
    kpi4.metric("Eficiencia de Entregas", "96.4%", "+2.1%")
    
    st.markdown("---")
    
    col_r1, col_r2 = st.columns(2)
    
    with col_r1:
        st.subheader("📈 Consumo Estimado por Tipo de Vehículo")
        datos_consumo = pd.DataFrame({
            "Vehículo": ["Carro", "Turbo", "Camión", "Tractomula"],
            "Galones por 100km": [3.5, 7.2, 12.0, 18.5]
        })
        st.bar_chart(datos_consumo.set_index("Vehículo"))
        
    with col_r2:
        st.subheader("📑 Registro Histórico de Operaciones")
        datos_historicos = pd.DataFrame([
            {"Fecha": "2026-09-15", "Ruta": "Envigado -> Bogotá", "Vehículo": "Tractomula", "Tiempo (hrs)": 10.2, "Estado": "Completado"},
            {"Fecha": "2026-09-16", "Ruta": "Medellín -> Cali", "Vehículo": "Camión", "Tiempo (hrs)": 8.5, "Estado": "Completado"},
            {"Fecha": "2026-09-17", "Ruta": "Bogotá -> Bucaramanga", "Vehículo": "Turbo", "Tiempo (hrs)": 7.1, "Estado": "Completado"},
        ])
        st.table(datos_historicos)