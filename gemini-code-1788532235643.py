import streamlit as st
import folium
from streamlit_folium import st_folium
import math
import datetime

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN INICIAL DE LA APLICACIÓN
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="RutaCarga - Sistema de Navegación Pesada",
    layout="wide",
    page_icon="🚛"
)

# -----------------------------------------------------------------------------
# 2. BASES DE DATOS SIMULADAS (MEDELLÍN Y ÁREA METROPOLITANA)
# -----------------------------------------------------------------------------
# Puntos clave del corredor vial del Valle de Aburrá
PUNTOS_UBICACION = {
    "Caldas (Entrada Sur)": [6.0910, -75.6350],
    "Sabaneta (Zona Industrial / Mayorista)": [6.1500, -75.6150],
    "Medellín - Parques del Río / Soterrado": [6.2442, -75.5736],
    "Bello (Zona Industrial Norte)": [6.3300, -75.5550],
    "Girardota (Peaje Cabildo / Parque Ind.)": [6.3750, -75.4450]
}

# Vías estructuradas con restricciones de gálibo (altura), peso y número de ejes
VIAS_METROPOLITANAS = [
    {
        "nombre": "Avenida Regional / Autopista Sur (Corredor Principal)",
        "coordenadas": [[6.1500, -75.6150], [6.2442, -75.5736], [6.3300, -75.5550]],
        "max_ejes": 6,
        "max_peso_ton": 52.0,
        "max_altura_m": 4.6,
        "peajes_en_tramo": 0
    },
    {
        "nombre": "Soterrado Parques del Río (Restricción Severa de Altura)",
        "coordenadas": [[6.2400, -75.5760], [6.2460, -75.5740]],
        "max_ejes": 6,
        "max_peso_ton": 52.0,
        "max_altura_m": 4.1,  # Gálibo limitado
        "peajes_en_tramo": 0
    },
    {
        "nombre": "Avenida El Poblado (Restricción Urbana / Zonas de Cargue)",
        "coordenadas": [[6.1750, -75.5900], [6.2100, -75.5710]],
        "max_ejes": 2,
        "max_peso_ton": 10.0,
        "max_altura_m": 3.8,
        "peajes_en_tramo": 0
    },
    {
        "nombre": "Variante a Caldas - Salida a Nariño/Eje Cafetero",
        "coordenadas": [[6.0910, -75.6350], [6.1400, -75.6200]],
        "max_ejes": 6,
        "max_peso_ton": 52.0,
        "max_altura_m": 4.8,
        "peajes_en_tramo": 1
    }
]

# Puntos de Servicio (Hoteles, Restaurantes, Parqueaderos con convenio)
if "puntos_interes" not in st.session_state:
    st.session_state.puntos_interes = [
        {
            "nombre": "Parqueadero & Taller El Camionero - Caldas",
            "tipo": "Parqueadero / Taller",
            "lat": 6.0950,
            "lon": -75.6320,
            "destacado": True,
            "descripcion": "Espacio para 40 tractomulas, vigilado 24/7, restaurante y duchas."
        },
        {
            "nombre": "Restaurante La Parada del C3 - Girardota",
            "tipo": "Restaurante",
            "lat": 6.3750,
            "lon": -75.4450,
            "destacado": True,
            "descripcion": "Menú ejecutivo, amplio parqueadero con fácil maniobrabilidad."
        },
        {
            "nombre": "Hotel El Transportador - Copacabana",
            "tipo": "Hotel",
            "lat": 6.3450,
            "lon": -75.5100,
            "destacado": False,
            "descripcion": "Habitaciones con bahía de parqueo privada vigilada."
        }
    ]

# Estado global para alertas reportadas por la comunidad (Tipo Waze)
if "reportes_comunidad" not in st.session_state:
    st.session_state.reportes_comunidad = [
        {"tipo": "Báscula de Pesaje Activa", "lat": 6.3600, "lon": -75.4700, "detalle": "Control de peso de la Secretaría de Movilidad"},
        {"tipo": "Vehículo Varado en Vía", "lat": 6.2200, "lon": -75.5800, "detalle": "Mula varada carril derecho en Autopista Sur"}
    ]

# -----------------------------------------------------------------------------
# 3. FUNCIONES DE CÁLCULO
# -----------------------------------------------------------------------------
def calcular_distancia(coord1, coord2):
    """Calcula distancia euclidiana aproximada en kilómetros (Haversine)."""
    R = 6371.0
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 1)

def estimar_costos(distancia_km, tipo_vehiculo):
    """Estima costo de peajes y combustible (ACPM) según categoría."""
    if "C2" in tipo_vehiculo:
        galon_por_km = 0.12  # ~8.3 km por galón
        precio_peaje_promedio = 15000
    elif "C3" in tipo_vehiculo:
        galon_por_km = 0.18  # ~5.5 km por galón
        precio_peaje_promedio = 22000
    else:  # C3S3
        galon_por_km = 0.25  # ~4.0 km por galón
        precio_peaje_promedio = 35000

    precio_acpm_galon = 9800  # Valor promedio estimado en COP
    costo_acpm = int(distancia_km * galon_por_km * precio_acpm_galon)
    
    # Simulación de un peaje estándar según distancia
    num_peajes = 1 if distancia_km > 20 else 0
    costo_peajes = num_peajes * precio_peaje_promedio

    return costo_acpm, costo_peajes, costo_acpm + costo_peajes

# -----------------------------------------------------------------------------
# 4. PANEL LATERAL DE CONTROL
# -----------------------------------------------------------------------------
st.sidebar.title("🚛 RutaCarga App")
st.sidebar.markdown("**Área Metropolitana de Medellín**")

menu = st.sidebar.radio("Módulos del Sistema", [
    "🗺️ Mapa & Calculadora de Rutas",
    "⚠️ Reportar Novedad (Comunidad)",
    "🏬 Registro de Comercios",
    "💳 Suscripción & Comercial"
])

# Parámetros globales del vehículo
st.sidebar.markdown("---")
st.sidebar.subheader("🚚 Ficha del Vehículo")
tipo_vehiculo = st.sidebar.selectbox("Configuración de Carga", ["C2 (Sencillo)", "C3 (Doble Troque)", "C3S3 (Tractomula)"])
placa_ultimo_digito = st.sidebar.number_input("Último Dígito de Placa", min_value=0, max_value=9, value=5)
ejes = st.sidebar.slider("Número de Ejes", 2, 6, 6 if "C3S3" in tipo_vehiculo else (3 if "C3" in tipo_vehiculo else 2))
peso_total = st.sidebar.number_input("Peso Bruto Total (Toneladas)", 2.0, 52.0, 38.0, 1.0)
altura_vehiculo = st.sidebar.number_input("Altura Total (Metros)", 2.0, 4.8, 4.3, 0.1)

# -----------------------------------------------------------------------------
# 5. MÓDULO 1: MAPA Y CALCULADORA DE RUTAS
# -----------------------------------------------------------------------------
if menu == "🗺️ Mapa & Calculadora de Rutas":
    st.title("Navegación Inteligente para Vehículos de Carga")
    st.caption("Planificación automatizada según restricciones de infraestructura, pico y placa y costos aproximados.")

    # Alerta de Pico y Placa / Restricción de Carga Ambiental
    dia_actual = datetime.datetime.now().strftime("%A")
    # Regla simulada para el prototipo
    pico_y_placa_activo = (placa_ultimo_digito in [4, 5, 6, 7])
    
    if pico_y_placa_activo:
        st.warning(f"⚠️ **Restricción Ambiental / Movilidad:** La placa terminada en **{placa_ultimo_digito}** tiene restricción de circulación de 06:00 a 08:30 y 17:00 a 19:30 en vías urbanas del Valle de Aburrá. Utiliza preferencialmente la Avenida Regional.")

    # Selección de Origen y Destino
    col_a, col_b = st.columns(2)
    with col_a:
        origen_nombre = st.selectbox("Punto de Origen (A)", list(PUNTOS_UBICACION.keys()), index=0)
    with col_b:
        destino_nombre = st.selectbox("Punto de Destino (B)", list(PUNTOS_UBICACION.keys()), index=3)

    coord_origen = PUNTOS_UBICACION[origen_nombre]
    coord_destino = PUNTOS_UBICACION[destino_nombre]
    distancia_km = calcular_distancia(coord_origen, coord_destino)
    costo_acpm, costo_peajes, costo_total = estimar_costos(distancia_km, tipo_vehiculo)

    # Panel de Métricas Rápidas
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Distancia Estimada", f"{distancia_km} km")
    m2.metric("Costo ACPM Aprox.", f"${costo_acpm:,} COP")
    m3.metric("Peajes Estimados", f"${costo_peajes:,} COP")
    m4.metric("Costo Operativo Ruta", f"${costo_total:,} COP")

    # Evaluación de Viabilidad en la Ruta
    vias_no_aptas = []
    for via in VIAS_METROPOLITANAS:
        if altura_vehiculo > via["max_altura_m"]:
            vias_no_aptas.append(f"{via['nombre']} (Supera gálibo de {via['max_altura_m']}m)")
        elif peso_total > via["max_peso_ton"]:
            vias_no_aptas.append(f"{via['nombre']} (Supera límite de peso de {via['max_peso_ton']} Ton)")
        elif ejes > via["max_ejes"]:
            vias_no_aptas.append(f"{via['nombre']} (Supera ejes permitidos: {via['max_ejes']})")

    if vias_no_aptas:
        st.error("🚨 **Atención: Se detectaron restricciones en la ruta estándar:**")
        for restriccion in vias_no_aptas:
            st.write(f"- {restriccion}")
    else:
        st.success("✅ **Ruta 100% Apta:** Sin restricciones de gálibo ni peso para tu configuración actual.")

    # Generación del Mapa Interactivo (Folium)
    m = folium.Map(location=[6.2442, -75.5736], zoom_start=11)

    # Trazado directo entre Origen y Destino
    folium.Marker(coord_origen, popup=f"Origen: {origen_nombre}", icon=folium.Icon(color="green", icon="play")).add_to(m)
    folium.Marker(coord_destino, popup=f"Destino: {destino_nombre}", icon=folium.Icon(color="red", icon="stop")).add_to(m)
    folium.PolyLine([coord_origen, coord_destino], color="blue", weight=3, opacity=0.6, dash_array="5, 10").add_to(m)

    # Dibujar estado de vías
    for via in VIAS_METROPOLITANAS:
        es_transitable = (altura_vehiculo <= via["max_altura_m"]) and (peso_total <= via["max_peso_ton"]) and (ejes <= via["max_ejes"])
        color_linea = "green" if es_transitable else "red"
        
        popup_html = f"<b>{via['nombre']}</b><br>Estado: {'APTA' if es_transitable else 'RESTRINGIDA'}<br>Máx Altura: {via['max_altura_m']}m | Máx Peso: {via['max_peso_ton']} Ton"
        
        folium.PolyLine(
            via["coordenadas"],
            color=color_linea,
            weight=6,
            opacity=0.8,
            popup=popup_html,
            tooltip=f"{via['nombre']} ({'Permitida' if es_transitable else 'No permitida'})"
        ).add_to(m)

    # Dibujar Puntos de Interés
    for poi in st.session_state.puntos_interes:
        color_icono = "gold" if poi["destacado"] else "blue"
        folium.Marker(
            [poi["lat"], poi["lon"]],
            popup=f"<b>{poi['nombre']}</b><br>{poi['descripcion']}",
            tooltip=poi["nombre"],
            icon=folium.Icon(color=color_icono, icon="star" if poi["destacado"] else "info-sign")
        ).add_to(m)

    # Dibujar Reportes de Comunidad
    for rep in st.session_state.reportes_comunidad:
        folium.Marker(
            [rep["lat"], rep["lon"]],
            popup=f"<b>{rep['tipo']}</b><br>{rep['detalle']}",
            tooltip=f"ALERTA: {rep['tipo']}",
            icon=folium.Icon(color="orange", icon="warning-sign")
        ).add_to(m)

    st_folium(m, width=1100, height=520)

    # Convenciones del Mapa
    col_l1, col_l2, col_l3 = st.columns(3)
    col_l1.markdown("🟢 **Vía Permitida:** Apta para tu vehículo")
    col_l2.markdown("🔴 **Vía Restringida:** Riesgo de choque o fotomulta")
    col_l3.markdown("🟠 **Icono Naranja:** Alerta de comunidad en vivo")

# -----------------------------------------------------------------------------
# 6. MÓDULO 2: REPORTES EN TIEMPO REAL (ESTILO WAZE)
# -----------------------------------------------------------------------------
elif menu == "⚠️ Reportar Novedad (Comunidad)":
    st.title("Reporte de Novedades en Vía")
    st.write("Apoya a otros conductores notificando incidentes sobre los corredores viales.")

    with st.form("form_reporte"):
        tipo_novedad = st.selectbox("Tipo de Incidente", [
            "Báscula de Pesaje Activa",
            "Retén de Movilidad / Tránsito",
            "Vehículo Varado en Vía",
            "Cierre Parcial por Obras",
            "Inundación / Encharcamiento Bajo Puente"
        ])
        sector = st.text_input("Ubicación / Referencia (ej. Regional a la altura de Solla)")
        detalle = st.text_area("Detalle adicional")
        
        submit = st.form_submit_button("Publicar Alerta")
        if submit:
            # Agrega un reporte con coordenadas genéricas cerca del centro para el prototipo
            st.session_state.reportes_comunidad.append({
                "tipo": tipo_novedad,
                "lat": 6.2500,
                "lon": -75.5700,
                "detalle": f"{sector} - {detalle}"
            })
            st.success("¡Alerta registrada y visible en el mapa para todos los conductores!")

# -----------------------------------------------------------------------------
# 7. MÓDULO 3: REGISTRO DE COMERCIOS (MONETIZACIÓN)
# -----------------------------------------------------------------------------
elif menu == "🏬 Registro de Comercios":
    st.title("Plataforma para Comercios Viales")
    st.write("Registra tu parqueadero, restaurante u hotel para aparecer destacado en las rutas de los transportadores de carga.")

    with st.form("form_comercio"):
        nombre_negocio = st.text_input("Nombre del Establecimiento")
        tipo_servicio = st.selectbox("Tipo de Servicio", ["Parqueadero de Carga", "Restaurante con Parqueo", "Hotel con Bahía", "Taller / Montallantas"])
        latitud = st.number_input("Latitud GPS", value=6.2442, format="%.4f")
        longitud = st.number_input("Longitud GPS", value=-75.5736, format="%.4f")
        descripcion = st.text_area("Servicios offered (ej. Parqueadero vigilado, duchas, menú ejecutivo)")
        es_patrocinado = st.checkbox("Activar Plan Destacado Dorado ($50.000 COP/mes)")

        submit_comercio = st.form_submit_button("Guardar Establecimiento")
        if submit_comercio:
            st.session_state.puntos_interes.append({
                "nombre": nombre_negocio,
                "tipo": tipo_servicio,
                "lat": latitud,
                "lon": longitud,
                "destacado": es_patrocinado,
                "descripcion": descripcion
            })
            st.success(f"¡Establecimiento '{nombre_negocio}' agregado con éxito al mapa de rutas!")

# -----------------------------------------------------------------------------
# 8. MÓDULO 4: SUSCRIPCIÓN Y MODELO COMERCIAL
# -----------------------------------------------------------------------------
elif menu == "💳 Suscripción & Comercial":
    st.title("Planes de Suscripción y Monetización")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Plan Transportador")
        st.write("### $25.000 COP / mes")
        st.markdown("""
        - Calculadora ilimitada de gálibo y peso
        - Alertas en tiempo real de básculas y retenes
        - Descuentos en restaurantes y parqueaderos aliados
        """)
        if st.button("Activar Suscripción Conductor"):
            st.info("Simulación: Conectando con MercadoPago / Wompi...")

    with col2:
        st.subheader("Plan Flotas / Generadores de Carga")
        st.write("### $200.000 COP / mes")
        st.markdown("""
        - Monitoreo de hasta 15 vehículos simultáneos
        - Historial de costos operacionales (ACPM/Peajes)
        - Integración directa con decretos municipales de tránsito
        """)
        if st.button("Activar Suscripción Empresa"):
            st.info("Simulación: Redirigiendo a pasarela corporativa...")