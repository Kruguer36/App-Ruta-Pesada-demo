import streamlit as st
import folium
from streamlit_folium import st_folium
import streamlit.components.v1 as components
import pandas as pd
import datetime
import math
import io
import json
import requests
import urllib.parse

# ==========================================
# 1. CONFIGURACIÓN INICIAL DE LA APP
# ==========================================
st.set_page_config(
    page_title="RutaCarga Aburrá - Navegador GPS & Waze",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Coordenadas base (Valle de Aburrá / Envigado)
ENVIGADO_LAT = 6.17591
ENVIGADO_LON = -75.59174

# ==========================================
# 2. FUNCIONES DE APOYO (GEOCERCAS, BUSCADOR Y OSRM)
# ==========================================
def calcular_distancia_metros(lat1, lon1, lat2, lon2):
    """Calcula la distancia Haversine en metros entre dos coordenadas."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def normalizar_texto(texto):
    """Normaliza abreviaturas comunes en direcciones colombianas."""
    reemplazos = {"cra": "Carrera", "cll": "Calle", "tv": "Transversal", "dg": "Diagonal", "cq": "Circular"}
    palabras = [reemplazos.get(p.lower().replace(".", ""), p) for p in texto.split()]
    return " ".join(palabras)

def buscar_lugar_nominatim(query):
    """Busca lugares en el Valle de Aburrá usando la API de Nominatim."""
    texto_limpio = normalizar_texto(query)
    q_norm = urllib.parse.quote(f"{texto_limpio}, Antioquia, Colombia")
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={q_norm}&viewbox=-75.68,6.38,-75.48,6.08"
    headers = {'User-Agent': 'RutaCarga_Waze_App'}
    try:
        resp = requests.get(url, headers=headers, timeout=5).json()
        if resp:
            return float(resp[0]['lat']), float(resp[0]['lon']), resp[0]['display_name'].split(',')[0]
    except Exception:
        pass
    return None, None, None

def obtener_geometria_osrm(puntos):
    """Obtiene trazado vial exacto e instrucciones de giro Waze desde OSRM."""
    if len(puntos) < 2:
        return [[p["lat"], p["lon"]] for p in puntos], 0.0, 0.0, []
    
    coords_str = ";".join([f"{p['lon']},{p['lat']}" for p in puntos])
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}?overview=full&geometries=geojson&steps=true"
    
    try:
        resp = requests.get(url, timeout=5).json()
        if resp.get("code") == "Ok":
            ruta = resp["routes"][0]
            geometria = [[lat, lon] for lon, lat in ruta["geometry"]["coordinates"]]
            dist_km = ruta["distance"] / 1000.0
            dur_min = ruta["duration"] / 60.0
            
            pasos = []
            for leg in ruta["legs"]:
                for step in leg["steps"]:
                    nombre_calle = step.get("name", "Vía local")
                    tipo_maniobra = step.get("maneuver", {}).get("type", "continuar")
                    pasos.append(f"{tipo_maniobra.upper()} en {nombre_calle}")
            return geometria, dist_km, dur_min, pasos
    except Exception:
        pass
    
    return [[p["lat"], p["lon"]] for p in puntos], 0.0, 0.0, ["Sin conexión OSRM - Navegando por línea recta"]

def obtener_ubicacion_gps():
    """Componente HTML/JS para capturar la ubicación GPS real del dispositivo."""
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

# ==========================================
# 3. CONTROL DE ESTADO DE SESIÓN (SESSION STATE)
# ==========================================
if "user_lat" not in st.session_state:
    st.session_state.user_lat = 6.1500
if "user_lon" not in st.session_state:
    st.session_state.user_lon = -75.6150
if "en_ruta" not in st.session_state:
    st.session_state.en_ruta = False
if "paso_animacion" not in st.session_state:
    st.session_state.paso_animacion = 0

if "puntos_ruta" not in st.session_state:
    st.session_state.puntos_ruta = [
        {"id": 1, "nombre": "Inicio - Sabaneta Industrial", "lat": 6.1500, "lon": -75.6150, "tipo": "Inicio", "completado": False},
        {"id": 2, "nombre": "Puente La Aguacatala (Restricción)", "lat": 6.1980, "lon": -75.5780, "tipo": "CheckPoint", "completado": False},
        {"id": 3, "nombre": "Destino - Terminal Niquía Bello", "lat": 6.3300, "lon": -75.5500, "tipo": "Fin", "completado": False}
    ]

if "alertas_comunidad" not in st.session_state:
    st.session_state.alertas_comunidad = [
        {"tipo": "Control / Fotomulta", "lat": 6.2100, "lon": -75.5720, "descripcion": "Radar de velocidad activo"},
        {"tipo": "Congestión Alta", "lat": 6.3300, "lon": -75.5550, "descripcion": "Obras en la vía a Bello"}
    ]

# ==========================================
# 4. BARRA LATERAL: CONFIGURACIÓN VEHÍCULO
# ==========================================
st.sidebar.title("🚛 RutaCarga Aburrá")
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

# ==========================================
# 5. DATOS BASE DE INFRAESTRUCTURA
# ==========================================
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

# ==========================================
# 6. MENÚ DE NAVEGACIÓN Y MÓDULOS
# ==========================================
st.title("🚚 RutaCarga: Navegador GPS & Waze para Carga Pesada")
st.caption("Navegación en tiempo real, restricciones de gálibo/peso y trazado vial interactivo OSRM.")

opcion_menu = st.radio(
    "Módulos del Sistema:",
    ["🧭 Navegador GPS & Rutas Waze", "🛠️ Programador de Rutas", "📢 Reportar Novedad", "🏪 Registro de Comercios", "💳 Planes & Monetización"],
    horizontal=True
)

# --- MÓDULO 1: NAVEGADOR GPS & WAZE ---
if "Navegador" in opcion_menu:
    col_controles, col_mapa = st.columns([1, 2])

    with col_controles:
        st.subheader("📍 Ubicación y Destino")
        gps_datos = obtener_ubicacion_gps()
        if gps_datos and isinstance(gps_datos, dict) and "lat" in gps_datos:
            st.session_state.user_lat = gps_datos["lat"]
            st.session_state.user_lon = gps_datos["lon"]
            st.session_state.puntos_ruta[0]["lat"] = gps_datos["lat"]
            st.session_state.puntos_ruta[0]["lon"] = gps_datos["lon"]
            st.success(f"📍 GPS Detectado: Lat {st.session_state.user_lat:.4f}, Lon {st.session_state.user_lon:.4f}")

        destino_seleccionado = st.selectbox("Destino Rápido:", list(destinos_aburra.keys()))
        if st.button("🎯 Fijar Destino"):
            dest_lat, dest_lon = destinos_aburra[destino_seleccionado]
            st.session_state.puntos_ruta[-1] = {
                "id": len(st.session_state.puntos_ruta),
                "nombre": f"Destino - {destino_seleccionado}",
                "lat": dest_lat,
                "lon": dest_lon,
                "tipo": "Fin",
                "completado": False
            }
            st.rerun()

        st.markdown("---")
        st.subheader("⚠️ Análisis de Seguridad")
        alerta_galibo = False
        if altura_metros > 3.6:
            st.error(f"❌ **Ruta no apta por gálibo:** Vehículo ({altura_metros}m) excede Puente La Aguacatala (3.6m).")
            st.warning("🔄 **Desvío Sugerido:** Tomar la Vía Regional por el carril oriental.")
            alerta_galibo = True
        else:
            st.success("✅ Vehículo dentro del límite de gálibo permitido.")

        # OSRM Geometría y Pasos
        geometria, dist_total, tiempo_total, pasos = obtener_geometria_osrm(st.session_state.puntos_ruta)

        st.markdown("---")
        st.subheader("💰 Estimación de Costos")
        precio_galon_acpm = 10150
        consumo_galones = dist_total / (6.5 if peso_toneladas > 20 else 9.0)
        costo_combustible = consumo_galones * precio_galon_acpm
        peajes = 16500 if "Tractocamión" in tipo_vehiculo else 9800

        st.write(f"• **Distancia Vial:** {dist_total:.2f} km")
        st.write(f"• **Tiempo Estimado:** {tiempo_total:.1f} min")
        st.write(f"• **ACPM Estimado:** {consumo_galones:.1f} gal (${costo_combustible:,.0f} COP)")
        st.write(f"• **Peajes:** ${peajes:,.0f} COP")
        st.metric("Total Estimado", f"${(costo_combustible + peajes):,.0f} COP")

    with col_mapa:
        # HUD Waze
        if pasos:
            idx_paso = min(int((st.session_state.paso_animacion / max(len(geometria), 1)) * len(pasos)), len(pasos) - 1)
            instruccion_actual = pasos[idx_paso]
        else:
            instruccion_actual = "Calculando trazado..."

        st.info(f"🚘 **HUD Waze:** {instruccion_actual}")

        # Controles de Simulación Waze
        c_sim1, c_sim2, c_sim3 = st.columns(3)
        with c_sim1:
            if st.button("▶️ Avanzar Vehículo"):
                if st.session_state.paso_animacion < len(geometria) - 1:
                    st.session_state.paso_animacion += max(1, len(geometria) // 15)
                    st.rerun()
                else:
                    st.success("🏁 ¡Has llegado a tu destino!")
        with c_sim2:
            if st.button("⏹️ Reiniciar Posición"):
                st.session_state.paso_animacion = 0
                st.rerun()

        # Posición actual en la simulación
        pos_vehiculo = geometria[min(st.session_state.paso_animacion, len(geometria) - 1)] if geometria else [st.session_state.user_lat, st.session_state.user_lon]

        # Mapa Folium
        m = folium.Map(location=pos_vehiculo, zoom_start=13)

        # Trazado OSRM
        color_linea = "red" if alerta_galibo else "#0096FF"
        folium.PolyLine(geometria, color=color_linea, weight=6, opacity=0.8, tooltip="Ruta Óptima OSRM").add_to(m)

        # Vehículo en ruta
        folium.Marker(
            pos_vehiculo,
            popup="Vehículo en Trayecto",
            icon=folium.Icon(color="red", icon="truck", prefix="fa")
        ).add_to(m)

        # Capas opcionales
        if mostrar_pois:
            for p in pois_data:
                folium.Marker([p["lat"], p["lon"]], popup=f"<b>{p['nombre']}</b><br>{p['detalles']}", icon=folium.Icon(color="cadetblue", icon="info-sign")).add_to(m)

        if mostrar_restricciones:
            for r in restricciones_data:
                folium.Marker([r["lat"], r["lon"]], popup=f"<b>{r['nombre']}</b><br>{r['detalles']}", icon=folium.Icon(color="orange", icon="exclamation-sign")).add_to(m)

        if mostrar_alertas:
            for a in st.session_state.alertas_comunidad:
                folium.Marker([a["lat"], a["lon"]], popup=f"<b>{a['tipo']}</b><br>{a['descripcion']}", icon=folium.Icon(color="darkred", icon="warning-sign")).add_to(m)

        st_folium(m, width="100%", height=500)

        with st.expander("📋 Ver Lista Completa de Giro a Giro (Steps)"):
            for i, p in enumerate(pasos, 1):
                st.write(f"**{i}.** {p}")

# --- MÓDULO 2: PROGRAMADOR DE RUTAS (BUSCADOR NOMINATIM) ---
elif "Programador" in opcion_menu:
    st.subheader("🛠️ Programar Paradas y Checkpoints (Buscador Waze)")
    
    col_b1, col_b2 = st.columns([3, 1])
    with col_b1:
        input_sitio = st.text_input("Buscar dirección o punto de referencia:", placeholder="Ej: Transversal 35C Sur Envigado, Dollarcity, Parque Envigado")
    with col_b2:
        st.write(" ")
        st.write(" ")
        if st.button("➕ Buscar y Cargar"):
            if input_sitio:
                lat_f, lon_f, nom_f = buscar_lugar_nominatim(input_sitio)
                if lat_f:
                    st.session_state["temp_lat"] = lat_f
                    st.session_state["temp_lon"] = lon_f
                    st.session_state["temp_nom"] = f"{input_sitio} ({nom_f})"
                    st.success("¡Ubicación encontrada en el Valle de Aburrá!")
                else:
                    st.error("No se pudo geolocalizar la dirección.")

    st.markdown("---")
    with st.form("form_add_punto"):
        nombre_default = st.session_state.get("temp_nom", "")
        lat_default = st.session_state.get("temp_lat", ENVIGADO_LAT)
        lon_default = st.session_state.get("temp_lon", ENVIGADO_LON)

        nombre = st.text_input("Nombre de la Parada:", value=nombre_default)
        lat = st.number_input("Latitud:", value=lat_default, format="%.5f")
        lon = st.number_input("Longitud:", value=lon_default, format="%.5f")
        tipo = st.selectbox("Tipo de Punto:", ["CheckPoint", "Giro", "Inicio", "Fin"])

        if st.form_submit_button("➕ Añadir Punto a la Ruta"):
            st.session_state.puntos_ruta.append({
                "id": len(st.session_state.puntos_ruta) + 1,
                "nombre": nombre if nombre else f"Punto {len(st.session_state.puntos_ruta) + 1}",
                "lat": lat,
                "lon": lon,
                "tipo": tipo,
                "completado": False
            })
            st.success("Punto añadido exitosamente.")
            st.rerun()

    st.subheader("Lista de Puntos Configurados")
    df_puntos = pd.DataFrame(st.session_state.puntos_ruta)
    st.dataframe(df_puntos[["id", "nombre", "tipo", "lat", "lon"]], use_container_width=True)

    if st.button("🗑️ Limpiar / Eliminar Último Punto"):
        if len(st.session_state.puntos_ruta) > 0:
            st.session_state.puntos_ruta.pop()
            st.rerun()

# --- MÓDULO 3: COMUNIDAD ---
elif "Reportar" in opcion_menu:
    st.subheader("📢 Reportar Novedad en la Vía")
    col1, col2 = st.columns(2)
    with col1:
        tipo_novedad = st.selectbox("Tipo de Alerta", ["Fotomulta Móvil", "Accidente / Vía Cerrada", "Retén de Control", "Vía en Mal Estado"])
        sector = st.text_input("Sector / Referencia", placeholder="Ej: Autopista Sur a la altura de Itagüí")
    with col2:
        detalles = st.text_area("Detalles para la comunidad", placeholder="Describa la situación...")
    if st.button("Enviar Alerta"):
        st.session_state.alertas_comunidad.append({
            "tipo": tipo_novedad,
            "lat": st.session_state.user_lat,
            "lon": st.session_state.user_lon,
            "descripcion": f"{sector} - {detalles}"
        })
        st.success("✅ Alerta compartida en tiempo real con la red de conductores.")

# --- MÓDULO 4: COMERCIOS ---
elif "Registro" in opcion_menu:
    st.subheader("🏪 Registra tu Comercio en la Red RutaCarga")
    with st.form("form_comercio"):
        nombre = st.text_input("Nombre del Establecimiento")
        categoria = st.selectbox("Categoría", ["Parqueadero Carga Pesada", "Restaurante con Parqueo", "Taller Mecánico", "Estación de Servicio"])
        contacto = st.text_input("Teléfono o WhatsApp")
        if st.form_submit_button("Solicitar Registro"):
            st.success("✅ Solicitud enviada. Te contactaremos pronto.")

# --- MÓDULO 5: PLANES ---
elif "Planes" in opcion_menu:
    st.subheader("💳 Planes de Suscripción y Monetización")
    c1, c2 = st.columns(2)
    with c1:
        st.info("### 🚛 Para Empresas y Flotas\n• Navegación GPS ilimitada con gálibo activo.\n• **$49.000 COP/mes**")
    with c2:
        st.success("### 🏪 Para Comercios en Ruta\n• Destaca tu negocio en el mapa interactivo.\n• **$89.000 COP/mes**")
