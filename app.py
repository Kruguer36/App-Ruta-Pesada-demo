import json
import time
import urllib.parse
import urllib.request
import pandas as pd
import pydeck as pdk
import streamlit as st

# Configuración de la aplicación
st.set_page_config(
    page_title="RutaCarga Colombia - Navegador GPS",
    page_icon="🚚",
    layout="wide"
)

# Inicialización del estado global
if "puntos_opcionales" not in st.session_state:
    st.session_state.puntos_opcionales = []
if "rutas_calculadas" not in st.session_state:
    st.session_state.rutas_calculadas = []
if "ruta_activa_idx" not in st.session_state:
    st.session_state.ruta_activa_idx = 0
if "simulacion_activa" not in st.session_state:
    st.session_state.simulacion_activa = False
if "paso_simulacion" not in st.session_state:
    st.session_state.paso_simulacion = 0

# --- FUNCIONES DE GEOCODIFICACIÓN Y RUTAS NACIONALES ---

def normalizar_texto(texto):
    reemplazos = {
        "cra": "Carrera", "cll": "Calle", "tv": "Transversal",
        "dg": "Diagonal", "cq": "Circular", "av": "Avenida"
    }
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

def obtener_color_vehiculo(tipo):
    colores = {
        "Carro": [231, 76, 60],       # Rojo
        "Turbo": [243, 156, 18],      # Naranja
        "Camión": [41, 128, 185],     # Azul
        "Tractomula": [142, 68, 173]  # Morado
    }
    return colores.get(tipo, [231, 76, 60])

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
                            tipo = step.get("maneuver", {}).get("type", "continuar")
                            instrucciones.append(f"{tipo.upper()} por {calle}")
                            
                    rutas.append({
                        "geometria": coords,
                        "distancia": dist_km,
                        "tiempo": dur_min,
                        "instrucciones": instrucciones,
                        "nombre": f"Opción {idx+1} ({'Principal' if idx==0 else 'Alternativa 2da Opción'})"
                    })
                return rutas
    except Exception as e:
        st.error(f"Error trazando ruta sobre red vial: {e}")
    return []

# --- MENÚ LATERAL ---
st.sidebar.title("🚚 RutaCarga Colombia")
modulo = st.sidebar.radio(
    "Seleccione Módulo:",
    ["1. Navegador GPS", "2. Programador", "3. Reportes", "4. Registro", "5. Planes"]
)

# --- MÓDULO 1: NAVEGADOR GPS ---
if modulo == "1. Navegador GPS":
    st.header("🧭 Navegador GPS Colombia (Trazo Vial y Simulación en Vivo)")
    
    col_control, col_mapa = st.columns([1, 2])
    
    # --- TABLERO DE CONTROL E INGRESO DE DATOS ---
    with col_control:
        st.subheader("📋 Tablero de Ingreso de Datos")
        
        vehiculo = st.selectbox("🚚 Tipo de Vehículo", ["Carro", "Turbo", "Camión", "Tractomula"])
        
        input_a = st.text_input("🟢 Punto A (Origen)", value="Envigado, Antioquia")
        input_b = st.text_input("🔴 Punto B (Destino)", value="Bogota, Cundinamarca")
        
        st.markdown("---")
        st.markdown("**🟡 Parada Intermedia (Opcional)**")
        input_opcional = st.text_input("Ingresar lugar/municipio de parada", value="Manizales, Caldas")
        
        col_p1, col_p2 = st.columns(2)
        if col_p1.button("➕ Agregar Parada"):
            if input_opcional.strip():
                pt = buscar_lugar_colombia(input_opcional)
                if pt:
                    st.session_state.puntos_opcionales.append({"nombre": input_opcional, "point": pt})
                    st.success(f"Parada añadida: {input_opcional}")
                else:
                    st.error("Ubicación no encontrada en Colombia.")
                    
        if col_p2.button("🗑️ Limpiar Paradas"):
            st.session_state.puntos_opcionales.clear()
            st.info("Paradas removidas.")
            
        if st.session_state.puntos_opcionales:
            st.write("**Paradas agendadas:**")
            for p in st.session_state.puntos_opcionales:
                st.caption(f"• {p['nombre']}")

        st.markdown("---")
        if st.button("🚀 Trazar y Calcular Ruta", type="primary", use_container_width=True):
            with st.spinner("Buscando coordenadas y trazando red vial de Colombia..."):
                pt_a = buscar_lugar_colombia(input_a)
                pt_b = buscar_lugar_colombia(input_b)
                
                if pt_a and pt_b:
                    rutas = calcular_rutas_osrm(pt_a, pt_b, st.session_state.puntos_opcionales)
                    if rutas:
                        st.session_state.rutas_calculadas = rutas
                        st.session_state.ruta_activa_idx = 0
                        st.session_state.paso_simulacion = 0
                        st.session_state.simulacion_activa = False
                    else:
                        st.error("No se encontraron vías transitables entre los puntos.")
                else:
                    st.error("Asegúrate de ingresar un Origen y Destino válidos.")

        # SELECCIÓN Y DATOS DE LA RUTA CALCULADA
        if st.session_state.rutas_calculadas:
            st.markdown("---")
            st.subheader("🔀 Opciones de Ruta")
            
            opciones_rutas = [r["nombre"] for r in st.session_state.rutas_calculadas]
            idx_sel = st.selectbox(
                "Seleccionar Alternativa:", 
                range(len(opciones_rutas)), 
                format_func=lambda x: opciones_rutas[x]
            )
            
            if idx_sel != st.session_state.ruta_activa_idx:
                st.session_state.ruta_activa_idx = idx_sel
                st.session_state.paso_simulacion = 0
                st.session_state.simulacion_activa = False
            
            ruta_sel = st.session_state.rutas_calculadas[st.session_state.ruta_activa_idx]
            
            st.info(f"**Distancia Total:** {ruta_sel['distancia']:.2f} km\n\n**Tiempo Estimado:** {ruta_sel['tiempo']/60:.1f} horas ({ruta_sel['tiempo']:.0f} min)")
            
            st.markdown("---")
            st.subheader("▶️ Control del Cursor de Navegación")
            
            col_s1, col_s2 = st.columns(2)
            if col_s1.button("▶️ Iniciar Recorrido", use_container_width=True):
                st.session_state.simulacion_activa = True
            if col_s2.button("⏹️ Detener / Pausar", use_container_width=True):
                st.session_state.simulacion_activa = False
                
            if st.button("🧹 Limpiar Mapa Completo", use_container_width=True):
                st.session_state.puntos_opcionales.clear()
                st.session_state.rutas_calculadas.clear()
                st.session_state.simulacion_activa = False
                st.session_state.paso_simulacion = 0
                st.rerun()

    # --- LIENZO DEL MAPA INTERACTIVO ---
    with col_mapa:
        if st.session_state.rutas_calculadas:
            ruta_activa = st.session_state.rutas_calculadas[st.session_state.ruta_activa_idx]
            coords = ruta_activa["geometria"]
            
            if st.session_state.simulacion_activa:
                if st.session_state.paso_simulacion < len(coords) - 1:
                    st.session_state.paso_simulacion += 1
                else:
                    st.session_state.simulacion_activa = False
                    st.success("🏁 ¡Has completado la ruta trazada!")

            pos_actual = coords[st.session_state.paso_simulacion]
            
            idx_instr = min(
                int((st.session_state.paso_simulacion / len(coords)) * len(ruta_activa["instrucciones"])),
                len(ruta_activa["instrucciones"]) - 1
            )
            st.warning(f"🚚 **Vehículo ({vehiculo}):** {ruta_activa['instrucciones'][idx_instr]}")

            color_veh = obtener_color_vehiculo(vehiculo)
            layers = []
            
            for i, r in enumerate(st.session_state.rutas_calculadas):
                es_activa = (i == st.session_state.ruta_activa_idx)
                layers.append(
                    pdk.Layer(
                        "PathLayer",
                        data=[{"path": r["geometria"]}],
                        get_path="path",
                        get_color=[0, 120, 255, 230] if es_activa else [160, 160, 160, 160],
                        width_scale=1,
                        width_min_pixels=6 if es_activa else 3,
                    )
                )

            df_vehiculo = pd.DataFrame([{"lon": pos_actual[0], "lat": pos_actual[1], "label": "✖"}])
            layers.append(
                pdk.Layer(
                    "TextLayer",
                    data=df_vehiculo,
                    get_position=["lon", "lat"],
                    get_text="label",
                    get_color=color_veh,
                    get_size=36,
                    get_alignment_baseline="'center'",
                )
            )

            view_state = pdk.ViewState(
                longitude=pos_actual[0],
                latitude=pos_actual[1],
                zoom=12,
                pitch=35
            )

            st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state))
            
            if st.session_state.simulacion_activa:
                time.sleep(0.08)
                st.rerun()
        else:
            view_state_colombia = pdk.ViewState(
                longitude=-74.1,
                latitude=4.6,
                zoom=5,
                pitch=0
            )
            st.pydeck_chart(pdk.Deck(initial_view_state=view_state_colombia))

# --- MÓDULOS ADICIONALES ---
elif modulo == "2. Programador":
    st.header("📅 Programador de Despachos")
    st.date_input("Fecha de Salida")
    st.time_input("Hora de Salida")
    st.selectbox("Asignar Conductor", ["Carlos Pérez", "Martha Gómez", "Juan Rodríguez"])

elif modulo == "3. Reportes":
    st.header("📊 Reportes y Métricas de Operación")
    st.metric(label="Total Rutas Completadas", value="142", delta="12%")

elif modulo == "4. Registro":
    st.header("📝 Registro de Vehículos y Conductores")
    st.text_input("Placa del Vehículo")

elif modulo == "5. Planes":
    st.header("💳 Planes y Suscripciones")
    st.write("Plan Pro - Rutas ilimitadas + Simulación GPS en vivo")