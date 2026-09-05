import streamlit as st
import folium
from streamlit_folium import st_folium
import streamlit.components.v1 as components

# Configuración inicial de la página
st.set_page_config(
    page_title="RutaCarga Aburrá - Navegador GPS",
    page_icon="🚛",
    layout="wide"
)

st.title("🚚 RutaCarga: Navegador GPS para Carga Pesada")
st.caption("Navegación en tiempo real, restricciones de gálibo/peso y servicios en ruta para el Valle de Aburrá.")

# --- COMPONENTE DE GEOLOCALIZACIÓN GPS (JavaScript) ---
def obtener_ubicacion_gps():
    html_gps = """
    <script>
    function getLocation() {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(showPosition, showError);
      } else {
        alert("La geolocalización no es soportada por este navegador.");
      }
    }
    function showPosition(position) {
      const lat = position.coords.latitude;
      const lon = position.coords.longitude;
      window.parent.postMessage({
        type: 'streamlit:setComponentValue',
        value: {lat: lat, lon: lon}
      }, '*');
    }
    function showError(error) {
      alert("Error al obtener ubicación: " + error.message);
    }
    </script>
    <button onclick="getLocation()" style="
        background-color: #ff4b4b;
        color: white;
        border: none;
        padding: 10px 18px;
        border-radius: 8px;
        font-weight: bold;
        cursor: pointer;
        width: 100%;
        margin-bottom: 10px;
    ">📍 Obtener Mi Ubicación Actual (GPS)</button>
    """
    return components.html(html_gps, height=60)

# --- ESTADOS DE SESIÓN PARA UBICACIÓN ---
if "user_lat" not in st.session_state:
    st.session_state.user_lat = 6.1500  # Latitud por defecto (Itagüí / Sabaneta)
if "user_lon" not in st.session_state:
    st.session_state.user_lon = -75.6150  # Longitud por defecto

# --- BARRA LATERAL: CONFIGURACIÓN DEL VEHÍCULO ---
st.sidebar.header("⚙️ Especificaciones del Vehículo")
tipo_vehiculo = st.sidebar.selectbox(
    "Configuración",
    ["C2 (Rígido 2 ejes)", "C3 (Rígido 3 ejes)", "C3S2 (Tractocamión)", "C3S3 (Tractocamión 6 ejes)"]
)
peso_toneladas = st.sidebar.slider("Peso Bruto (Toneladas)", min_value=3.0, max_value=52.0, value=18.0, step=0.5)
altura_metros = st.sidebar.slider("Altura Total (Metros)", min_value=2.0, max_value=4.5, value=3.9, step=0.1)

st.sidebar.markdown("---")
st.sidebar.header("🎯 Capas del Mapa")
mostrar_pois = st.sidebar.checkbox("Mostrar POIs (Parqueaderos/Talleres)", value=True)
mostrar_restricciones = st.sidebar.checkbox("Mostrar Restricciones de Altura", value=True)
mostrar_alertas = st.sidebar.checkbox("Mostrar Reportes Comunidad", value=True)

# --- NAVEGACIÓN DE MÓDULOS ---
opcion_menu = st.radio(
    "Módulos del Sistema:",
    ["🧭 Navegador GPS & Rutas", "📢 Reportar Novedad", "🏪 Registro de Comercios", "💳 Planes & Monetización"],
    horizontal=True
)

# --- DATOS BASE DE INFRAESTRUCTURA Y POIs ---
destinos_aburra = {
    "Zona Industrial Sabaneta": [6.1500, -75.6150],
    "Zona Industrial Itagüí": [6.1720, -75.6080],
    "Centro de Logística Medellín (Sur)": [6.2100, -75.5800],
    "Terminal de Carga Bello / Niquía": [6.3300, -75.5500],
    "Parque Industrial Girardota": [6.3750, -75.4450]
}

pois_data = [
    {"nombre": "Parqueadero Carga Pesada Sabaneta", "tipo": "Parqueadero", "lat": 6.1500, "lon": -75.6150, "detalles": "Seguridad 24/7, Capacidad 40 mulas"},
    {"nombre": "Restaurante El Camionero (Girardota)", "tipo": "Restaurante", "lat": 6.3750, "lon": -75.4450, "detalles": "Espacio amplio, duchas"},
    {"nombre": "TecniCamiones Itagüí", "tipo": "Taller", "lat": 6.1720, "lon": -75.6080, "detalles": "Mecánica diésel y frenos"},
    {"nombre": "EDS Texaco Autopista Sur", "tipo": "Combustible", "lat": 6.1950, "lon": -75.5900, "detalles": "ACPM, alto gálibo"}
]

restricciones_data = [
    {"nombre": "Puente La Aguacatala", "lat": 6.1980, "lon": -75.5780, "max_altura": 3.6, "detalles": "Gálibo máximo 3.6m"},
    {"nombre": "Puente Pandequeso (Envigado)", "lat": 6.1750, "lon": -75.5910, "max_altura": 4.0, "detalles": "Gálibo máximo 4.0m"}
]

alertas_comunidad = [
    {"tipo": "Control / Fotomulta", "lat": 6.2100, "lon": -75.5720, "descripcion": "Radar de velocidad activo"},
    {"tipo": "Congestión Alta", "lat": 6.3300, "lon": -75.5550, "descripcion": "Obras en la vía a Bello"}
]

# --- MÓDULO 1: NAVEGADOR GPS ---
if "Navegador" in opcion_menu:
    col_controles, col_mapa = st.columns([1, 2])

    with col_controles:
        st.subheader("📍 Configurar Navegación")
        st.write("1. Haz clic abajo para detectar tu posición exacta:")
        
        # Botón para capturar GPS del teléfono
        gps_datos = obtener_ubicacion_gps()
        if gps_datos and isinstance(gps_datos, dict) and "lat" in gps_datos:
            st.session_state.user_lat = gps_datos["lat"]
            st.session_state.user_lon = gps_datos["lon"]
            st.success(f"📍 Ubicación detectada: Lat {st.session_state.user_lat:.4f}, Lon {st.session_state.user_lon:.4f}")

        st.write("2. Selecciona tu Destino:")
        destino_seleccionado = st.selectbox("Destino en el Valle de Aburrá", list(destinos_aburra.keys()))
        dest_lat, dest_lon = destinos_aburra[destino_seleccionado]

        st.markdown("---")
        st.subheader("⚠️ Análisis de Seguridad en Ruta")
        
        # Validación de Altura
        alerta_galibo = False
        if altura_metros > 3.6:
            st.error(f"❌ **Ruta no apta por gálibo:** Su vehículo ({altura_metros}m) excede el Puente La Aguacatala (3.6m).")
            st.warning("🔄 **Desvío Sugerido:** Tomar la Vía Regional por el carril oriental.")
            alerta_galibo = True
        else:
            st.success("✅ Vehículo dentro del límite de gálibo permitido para el trayecto.")

        st.markdown("---")
        st.subheader("💰 Estimación de Costos")
        distancia_estimada_km = 22.0
        precio_galon_acpm = 10150
        consumo_galones = distancia_estimada_km / (6.5 if peso_toneladas > 20 else 9.0)
        costo_combustible = consumo_galones * precio_galon_acpm
        peajes = 16500 if "Tractocamión" in tipo_vehiculo else 9800

        st.write(f"• **Distancia:** ~{distancia_estimada_km} km")
        st.write(f"• **ACPM Estimado:** {consumo_galones:.1f} gal (${costo_combustible:,.0f} COP)")
        st.write(f"• **Peajes:** ${peajes:,.0f} COP")
        st.metric("Total Estimado", f"${(costo_combustible + peajes):,.0f} COP")

    with col_mapa:
        # Mapa centrado en la ubicación actual del usuario o teléfono
        m = folium.Map(location=[st.session_state.user_lat, st.session_state.user_lon], zoom_start=12)

        # Marcador ORIGEN (Ubicación actual del teléfono)
        folium.Marker(
            location=[st.session_state.user_lat, st.session_state.user_lon],
            popup="<b>Tu Ubicación Actual</b>",
            tooltip="Origen (Tú)",
            icon=folium.Icon(color="green", icon="user", prefix="fa")
        ).add_to(m)

        # Marcador DESTINO
        folium.Marker(
            location=[dest_lat, dest_lon],
            popup=f"<b>Destino:</b> {destino_seleccionado}",
            tooltip=f"Destino: {destino_seleccionado}",
            icon=folium.Icon(color="red", icon="flag")
        ).add_to(m)

        # Línea de Navegación / Ruta
        color_linea = "red" if alerta_galibo else "blue"
        puntos_ruta = [
            [st.session_state.user_lat, st.session_state.user_lon],
            [(st.session_state.user_lat + dest_lat) / 2, (st.session_state.user_lon + dest_lon) / 2],
            [dest_lat, dest_lon]
        ]
        folium.PolyLine(puntos_ruta, color=color_linea, weight=6, opacity=0.8, tooltip="Ruta de Carga").add_to(m)

        # Mostrar POIs
        if mostrar_pois:
            for p in pois_data:
                folium.Marker(
                    location=[p["lat"], p["lon"]],
                    popup=f"<b>{p['nombre']}</b><br>{p['detalles']}",
                    tooltip=f"{p['tipo']}: {p['nombre']}",
                    icon=folium.Icon(color="cadetblue", icon="info-sign")
                ).add_to(m)

        # Mostrar Restricciones
        if mostrar_restricciones:
            for r in restricciones_data:
                folium.Marker(
                    location=[r["lat"], r["lon"]],
                    popup=f"<b>{r['nombre']}</b><br>{r['detalles']}",
                    tooltip=f"Restricción: {r['nombre']}",
                    icon=folium.Icon(color="orange", icon="exclamation-sign")
                ).add_to(m)

        # Mostrar Alertas
        if mostrar_alertas:
            for a in alertas_comunidad:
                folium.Marker(
                    location=[a["lat"], a["lon"]],
                    popup=f"<b>{a['tipo']}</b><br>{a['descripcion']}",
                    tooltip=f"Alerta: {a['tipo']}",
                    icon=folium.Icon(color="darkred", icon="warning-sign")
                ).add_to(m)

        st_folium(m, width=800, height=550)

# --- MÓDULO 2: COMUNIDAD ---
elif "Reportar" in opcion_menu:
    st.subheader("📢 Reportar Novedad en la Vía")
    col1, col2 = st.columns(2)
    with col1:
        tipo_novedad = st.selectbox("Tipo de Alerta", ["Fotomulta Móvil", "Accidente / Vía Cerrada", "Retén de Control", "Vía en Mal Estado"])
        sector = st.text_input("Sector / Referencia", placeholder="Ej: Autopista Sur a la altura de Itagüí")
    with col2:
        detalles = st.text_area("Detalles para la comunidad", placeholder="Describa la situación...")
    if st.button("Enviar Alerta"):
        st.success("✅ Alerta compartida en tiempo real con la red de conductores.")

# --- MÓDULO 3: COMERCIOS ---
elif "Registro" in opcion_menu:
    st.subheader("🏪 Registra tu Comercio en la Red RutaCarga")
    with st.form("form_comercio"):
        nombre = st.text_input("Nombre del Establecimiento")
        categoria = st.selectbox("Categoría", ["Parqueadero Carga Pesada", "Restaurante con Parqueo", "Taller Mecánico", "Estación de Servicio"])
        contacto = st.text_input("Teléfono o WhatsApp")
        if st.form_submit_button("Solicitar Registro"):
            st.success("✅ Solicitud enviada. Te contactaremos pronto.")

# --- MÓDULO 4: PLANES ---
elif "Planes" in opcion_menu:
    st.subheader("💳 Planes de Suscripción y Monetización")
    c1, c2 = st.columns(2)
    with c1:
        st.info("### 🚛 Para Empresas y Flotas\n• Navegación GPS ilimitada con gálibo activo.\n• **$49.000 COP/mes**")
    with c2:
        st.success("### 🏪 Para Comercios en Ruta\n• Destaca tu negocio en el mapa interactivo.\n• **$89.000 COP/mes**")
