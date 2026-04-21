import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import io

st.set_page_config(page_title="Bike trasmission metrics")

TIRES = {
    "BDC (Road)": {
        "700x23": 2096, "700x25": 2105, "700x28": 2136,
        "700x30": 2146, "700x32": 2155,
    },
    "Gravel": {
        "700x35": 2168, "700x38": 2180, "700x40": 2200,
        "700x42": 2224, "700x45": 2242, "700x47": 2268, "700x50": 2320,
    },
    "MTB": {
        "26x1.75": 2035, "26x2.00": 2075, "26x2.10": 2091,
        "26x2.25": 2115, "26x2.30": 2123, "26x2.35": 2131,
        "26x2.40": 2137, "26x2.50": 2155,
        "27.5x2.00": 2154, "27.5x2.10": 2170, "27.5x2.20": 2186,
        "27.5x2.25": 2194, "27.5x2.30": 2202, "27.5x2.35": 2210,
        "27.5x2.40": 2216, "27.5x2.50": 2234, "27.5x2.60": 2250,
        "29x2.00": 2273, "29x2.10": 2289, "29x2.20": 2305,
        "29x2.25": 2313, "29x2.30": 2321, "29x2.35": 2329,
        "29x2.40": 2335, "29x2.50": 2353, "29x2.60": 2369, "29x3.00": 2433,
    },
}

DEFAULT_SPROCKETS = [11, 13, 15, 17, 19, 21, 24, 28, 32, 36, 40]
COLORS = ["#1f77b4", "#9467bd", "#e377c2"]

def _pdf_filename(modello_bici, modello_trasmissione):
    import re
    def slug(s):
        return re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_")
    parts = ["report_trasmissione"]
    if modello_bici:
        parts.append(slug(modello_bici))
    if modello_trasmissione:
        parts.append(slug(modello_trasmissione))
    return "_".join(parts) + ".pdf"

def sviluppo(corona, pignone, circ_mm):
    return round((corona / pignone) * (circ_mm / 1000), 2)

def velocita(sv, rpm):
    return round(sv * rpm * 60 / 1000, 1)

def build_figures(df, corone, vmin_col, vmax_col, cadenza_min, cadenza_max, circ_mm):
    # fig: velocità
    fig = go.Figure()
    for i, corona in enumerate(corone):
        df_c = df[df["Corona"] == corona].sort_values("Pignone", ascending=False)
        c = COLORS[i]
        fig.add_trace(go.Scatter(
            x=df_c["Pignone"], y=df_c[vmax_col],
            name=f"Corona {corona}T @{cadenza_max} rpm",
            mode="lines+markers", line=dict(color=c, width=2, dash="dot"),
            marker=dict(size=6, color=c), legendgroup=str(corona),
        ))
        fig.add_trace(go.Scatter(
            x=df_c["Pignone"], y=df_c[vmin_col],
            name=f"Corona {corona}T @{cadenza_min} rpm",
            mode="lines+markers", line=dict(color=c, width=2),
            marker=dict(size=6, color=c), fill="tonexty", legendgroup=str(corona),
        ))
    all_pignoni = sorted(df["Pignone"].unique(), reverse=True)
    fig.update_layout(
        xaxis=dict(
            title="Pignone (denti)",
            autorange="reversed",
            tickmode="array",
            tickvals=all_pignoni,
            ticktext=[str(p) for p in all_pignoni],
        ),
        yaxis=dict(title="Velocità (km/h)"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
        margin=dict(l=50, r=10, t=10, b=100), height=420,
    )

    # fig2: rapporti + secondo asse sviluppo metrico
    sv_factor = circ_mm / 1000
    df_sorted = df.sort_values("Sviluppo (m)", ascending=True).reset_index(drop=True)
    df_sorted["Label"] = df_sorted["Corona"].astype(str) + "×" + df_sorted["Pignone"].astype(str)
    df_sorted["Var_prev"] = df_sorted["Sviluppo (m)"].pct_change(1).mul(100).round(1)
    df_sorted["Var_next"] = (
        df_sorted["Sviluppo (m)"].shift(-1)
        .sub(df_sorted["Sviluppo (m)"])
        .div(df_sorted["Sviluppo (m)"])
        .mul(100).round(1)
    )
    def _fmt_var(v):
        return "—" if pd.isna(v) else f"{v:+.1f}%"
    df_sorted["Var_prev_s"] = df_sorted["Var_prev"].apply(_fmt_var)
    df_sorted["Var_next_s"] = df_sorted["Var_next"].apply(_fmt_var)

    fig2 = go.Figure()
    for i, corona in enumerate(corone):
        df_c = df_sorted[df_sorted["Corona"] == corona]
        cd = list(zip(
            [corona] * len(df_c),
            df_c["Pignone"].astype(int).tolist(),
            df_c["Sviluppo (m)"].tolist(),
            df_c["Var_prev_s"].tolist(),
            df_c["Var_next_s"].tolist(),
        ))
        fig2.add_trace(go.Bar(
            x=df_c["Label"], y=df_c["Rapporto"],
            name="Corona " + str(corona) + "T", marker_color=COLORS[i],
            customdata=cd,
            hovertemplate=(
                "Corona: %{customdata[0]}T<br>"
                "Pignone: %{customdata[1]}T<br>"
                "Rapporto: %{y:.2f}<br>"
                "Sviluppo: %{customdata[2]:.2f} m<br>"
                "Var. prec.: %{customdata[3]}<br>"
                "Var. succ.: %{customdata[4]}"
                "<extra></extra>"
            ),
        ))
    r_max = df_sorted["Rapporto"].max() * 1.15
    tick_step = 0.5
    tick_vals = [round(i * tick_step, 1) for i in range(int(r_max / tick_step) + 2)
                 if i * tick_step <= r_max]
    tick_vals_sv = [round(v * sv_factor, 2) for v in tick_vals]
    fig2.add_trace(go.Scatter(
        x=[df_sorted["Label"].iloc[0], df_sorted["Label"].iloc[-1]],
        y=[0, r_max * sv_factor],
        yaxis="y2", mode="markers",
        marker=dict(opacity=0), showlegend=False, hoverinfo="skip",
    ))
    fig2.update_layout(
        barmode="group",
        xaxis=dict(title="", categoryorder="array",
                   categoryarray=df_sorted["Label"].tolist(), tickangle=-90),
        yaxis=dict(title="Rapporto", range=[0, r_max],
                   tickmode="array", tickvals=tick_vals,
                   ticktext=[f"{v:.1f}" for v in tick_vals]),
        yaxis2=dict(
            title="Sviluppo (m)",
            range=[0, r_max * sv_factor],
            overlaying="y", side="right",
            showgrid=False,
            tickmode="array",
            tickvals=tick_vals_sv,
            ticktext=[f"{v:.2f}" for v in tick_vals_sv],
        ),
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=50, r=80, t=10, b=60), height=420,
    )

    # fig3: sovrapposizione (solo multi-corona) — una linea per corona, un pallino per rapporto
    fig3 = None
    if len(corone) > 1:
        all_ratios = df.sort_values("Rapporto").copy()
        fig3 = go.Figure()
        for i, corona in enumerate(corone):
            df_c = all_ratios[all_ratios["Corona"] == corona].sort_values("Rapporto")
            df_c = df_c.sort_values("Rapporto")
            fig3.add_trace(go.Scatter(
                x=df_c["Rapporto"].tolist(), y=[i] * len(df_c),
                mode="markers",
                marker=dict(symbol="line-ns", size=16, color=COLORS[i],
                            line=dict(color=COLORS[i], width=2)),
                name=f"Corona {corona}T", showlegend=False,
                customdata=list(zip(
                    df_c["Pignone"].astype(int).tolist(),
                    df_c["Sviluppo (m)"].tolist(),
                )),
                hovertemplate=(
                    f"Corona: {corona}T<br>"
                    "Pignone: %{customdata[0]}T<br>"
                    "Rapporto: %{x:.2f}<br>"
                    "Sviluppo: %{customdata[1]:.2f} m<extra></extra>"
                ),
            ))
        row_lines = []
        for i, corona in enumerate(corone):
            df_c = all_ratios[all_ratios["Corona"] == corona]
            r_min, r_max_c = df_c["Rapporto"].min(), df_c["Rapporto"].max()
            row_lines.append(dict(
                type="line", xref="paper", yref="y",
                x0=0, x1=1, y0=i, y1=i,
                line=dict(color="lightgrey", width=1),
            ))
            row_lines.append(dict(
                type="line", xref="x", yref="y",
                x0=r_min, x1=r_max_c, y0=i, y1=i,
                line=dict(color=COLORS[i], width=2),
            ))
        fig3.update_layout(
            xaxis=dict(title="Rapporto (corona / pignone)"),
            yaxis=dict(
                tickmode="array",
                tickvals=list(range(len(corone))),
                ticktext=[f"{c}T" for c in corone],
                range=[-0.5, len(corone) - 0.5],
                showgrid=False,
            ),
            shapes=row_lines,
            hovermode="x",
            showlegend=False,
            margin=dict(l=60, r=10, t=10, b=80), height=100 + len(corone) * 60,
        )

    return fig, fig2, fig3

def genera_pdf(df, df_display, fig, fig2, fig3,
               bike_label, selected_tire, circ_mm, corone, pignoni,
               cadenza_min, cadenza_max, vmin_col, vmax_col,
               modello_bici="", modello_trasmissione=""):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable, PageBreak

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm)
    W = A4[0] - 30*mm
    styles = getSampleStyleSheet()
    title_style    = ParagraphStyle("t",  parent=styles["Title"],    fontSize=16, spaceAfter=2)
    subtitle_style = ParagraphStyle("st", parent=styles["Heading2"], fontSize=13, spaceAfter=2, spaceBefore=2)
    h2_style       = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=10, spaceBefore=8, spaceAfter=3)
    small_style    = ParagraphStyle("s",  parent=styles["Normal"],   fontSize=7,  textColor=colors.grey)
    story = []

    story.append(Paragraph("Report trasmissione", title_style))
    if modello_bici:
        story.append(Paragraph(modello_bici, subtitle_style))
    if modello_trasmissione:
        story.append(Paragraph(modello_trasmissione, subtitle_style))
    for line in [
        f"Bici: <b>{bike_label}</b>",
        f"Pneumatico: <b>{selected_tire}</b> ({circ_mm} mm)",
        f"Corone: <b>{', '.join(str(c)+'T' for c in corone)}</b>",
        f"Pignoni: <b>{', '.join(str(int(p))+'T' for p in sorted(pignoni))}</b>",
        f"Cadenza: <b>{cadenza_min}–{cadenza_max} rpm</b>",
    ]:
        story.append(Paragraph(line, small_style))
    story.append(HRFlowable(width=W, thickness=0.5, color=colors.lightgrey, spaceAfter=6))

    caption_style = ParagraphStyle("c", parent=styles["Normal"], fontSize=7,
                                   textColor=colors.grey, spaceAfter=4)

    def add_chart(f, title, caption=None, h=60*mm, w_px=900, h_px=400):
        story.append(Paragraph(title, h2_style))
        if caption:
            story.append(Paragraph(caption, caption_style))
        img_bytes = f.to_image(format="png", width=w_px, height=h_px, scale=2)
        story.append(RLImage(io.BytesIO(img_bytes), width=W, height=h))
        story.append(Spacer(1, 3*mm))

    add_chart(fig,  "Velocità", h=70*mm, h_px=420,
        caption="Velocità raggiungibile per ogni combinazione corona/pignone, nell'intervallo di cadenza selezionato. L'area colorata rappresenta il range di velocità tra cadenza minima e massima.")
    add_chart(fig2, "Rapporti", h=65*mm, h_px=420,
        caption="Valore di ogni rapporto (corona/pignone) e relativo sviluppo metrico (metri percorsi per pedalata). Le barre sono ordinate dal rapporto più agile al più duro. Un salto tra un rapporto e l'altro con una variazione intorno al 5-10% è considerato ottimale. Variazioni sotto il 5% indicano una ridondanza di rapporti. Variazioni sopra il 20% determinano un salto brusco.")
    if fig3 is not None:
        h3 = max(30*mm, 20*mm + len(corone) * 15*mm)
        h3_px = 100 + len(corone) * 60
        add_chart(fig3, "Sovrapposizione dei rapporti", h=h3, h_px=h3_px,
            caption="Ogni tacca rappresenta un rapporto disponibile. Tacche vicine o sovrapposte tra corone diverse indicano rapporti ridondanti; spazi vuoti indicano salti bruschi nella progressione.")

    story.append(PageBreak())
    story.append(Paragraph("Tabella rapporti", h2_style))
    tbl_data = [list(df_display.columns)] + [list(row) for _, row in df_display.iterrows()]
    col_w = W / len(df_display.columns)
    tbl = Table(tbl_data, colWidths=[col_w]*len(df_display.columns), repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",     (0,0), (-1,0),  colors.HexColor("#4B77FF")),
        ("TEXTCOLOR",      (0,0), (-1,0),  colors.white),
        ("FONTNAME",       (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",       (0,0), (-1,-1), 7),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f2f4f8")]),
        ("GRID",           (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("ALIGN",          (0,0), (-1,-1), "CENTER"),
        ("VALIGN",         (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",     (0,0), (-1,-1), 3),
        ("BOTTOMPADDING",  (0,0), (-1,-1), 3),
    ]))
    story.append(tbl)
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = None
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None
if "pdf_filename" not in st.session_state:
    st.session_state.pdf_filename = "report_trasmissione.pdf"

# ── RUOTE ─────────────────────────────────────────────────────────────────────
st.subheader("Ruote")
col_a, col_b = st.columns(2)
with col_a:
    bike_label = st.selectbox("Tipo di bicicletta", list(TIRES.keys()))
with col_b:
    selected_tire = st.selectbox("Pneumatico", list(TIRES[bike_label].keys()),
        help="La circonferenza della ruota determina quanta strada percorri per ogni giro completo.")
circ_mm = TIRES[bike_label][selected_tire]
st.caption(f"Circonferenza: {circ_mm} mm")

# ── GUARNITURA ────────────────────────────────────────────────────────────────
st.subheader("Guarnitura")
crank_type = st.selectbox("Tipo", ["Monocorona", "Doppia corona", "Tripla corona"],
    help="Le caratteristiche della corona anteriore (o delle corone). Inserisci il numero di corone e specifica il numero di denti.")
if crank_type == "Monocorona":
    col_c1, = st.columns(1)
    with col_c1:
        corona_1 = st.number_input("Denti corona", min_value=10, max_value=70, value=40, step=1)
    corone = [corona_1]
elif crank_type == "Doppia corona":
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        corona_s = st.number_input("Corona piccola", min_value=20, max_value=55, value=34, step=1)
    with col_c2:
        corona_g = st.number_input("Corona grande", min_value=40, max_value=70, value=50, step=1)
    corone = sorted([corona_s, corona_g])
else:
    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        corona_p = st.number_input("Corona piccola", min_value=20, max_value=55, value=30, step=1)
    with col_c2:
        corona_m = st.number_input("Corona media", min_value=25, max_value=55, value=39, step=1)
    with col_c3:
        corona_g = st.number_input("Corona grande", min_value=30, max_value=60, value=50, step=1)
    corone = sorted([corona_p, corona_m, corona_g])

# ── PIGNONI ───────────────────────────────────────────────────────────────────
st.subheader("Pignoni")
n_speeds = st.number_input("Numero di rapporti", min_value=1, max_value=13, value=11, step=1, key="n_speeds",
    help="Le caratteristiche della cassetta posteriore. Inserisci il numero di pignoni e il numero di denti per ogni pignone.")
n = int(n_speeds)
cols = st.columns(n)
pignoni = []
valid = True
for i, col in enumerate(cols):
    default = DEFAULT_SPROCKETS[i] if i < len(DEFAULT_SPROCKETS) else DEFAULT_SPROCKETS[-1]
    val = col.number_input(f"P{i+1}", min_value=9, max_value=60, value=default, step=1)
    pignoni.append(val)
if len(set(pignoni)) != len(pignoni):
    st.warning("Alcuni pignoni hanno lo stesso numero di denti.")
    valid = False

# ── CADENZA ───────────────────────────────────────────────────────────────────
st.subheader("Cadenza (rpm)")
cadenza_min, cadenza_max = st.slider("Cadenza", min_value=30, max_value=120,
    value=(50, 100), step=10, label_visibility="collapsed",
    help="Numero di pedalate al minuto. Il range tipico per un ciclista è 50–100 rpm. Definito il rapporto corone/pignoni e la cadenza, si può calcolare la velocità.")

# ── CALCOLA ───────────────────────────────────────────────────────────────────
if st.button("Calcola", type="primary", use_container_width=True):
    if not valid:
        st.error("Correggi i valori prima di calcolare.")
    else:
        vmin_col = f"Vel. @{cadenza_min} rpm (km/h)"
        vmax_col = f"Vel. @{cadenza_max} rpm (km/h)"
        rows = []
        for corona in corone:
            for pig in sorted(pignoni):
                sv = sviluppo(corona, pig, circ_mm)
                rows.append({
                    "Corona": corona, "Pignone": pig,
                    "Rapporto": round(corona / pig, 2),
                    "Sviluppo (m)": sv,
                    vmin_col: velocita(sv, cadenza_min),
                    vmax_col: velocita(sv, cadenza_max),
                })
        df = pd.DataFrame(rows).sort_values("Sviluppo (m)").reset_index(drop=True)
        df["Var. %"] = df["Sviluppo (m)"].pct_change().mul(100).round(1)
        df["Var. %"] = df["Var. %"].apply(lambda x: f"+{x:.1f}%" if pd.notna(x) else "—")
        fig, fig2, fig3 = build_figures(
            df, corone, vmin_col, vmax_col, cadenza_min, cadenza_max, circ_mm)
        df_display = df.copy()
        df_display["Rapporto"] = df_display["Rapporto"].apply(lambda x: f"{x:.2f}")
        df_display["Sviluppo (m)"] = df_display["Sviluppo (m)"].apply(lambda x: f"{x:.2f}")
        df_display[vmin_col] = df_display[vmin_col].apply(lambda x: f"{x:.1f}")
        df_display[vmax_col] = df_display[vmax_col].apply(lambda x: f"{x:.1f}")
        st.session_state.results = {
            "df": df, "df_display": df_display,
            "fig": fig, "fig2": fig2, "fig3": fig3,
            "vmin_col": vmin_col, "vmax_col": vmax_col,
            "bike_label": bike_label, "selected_tire": selected_tire,
            "circ_mm": circ_mm, "corone": corone, "pignoni": pignoni,
            "cadenza_min": cadenza_min, "cadenza_max": cadenza_max,
        }
        st.session_state.pdf_bytes = None  # reset pdf on new calc

# ── RISULTATI ─────────────────────────────────────────────────────────────────
if st.session_state.results is not None:
    r = st.session_state.results
    df         = r["df"]
    df_display = r["df_display"]
    fig        = r["fig"]
    fig2       = r["fig2"]
    fig3       = r["fig3"]
    vmin_col   = r["vmin_col"]
    vmax_col   = r["vmax_col"]
    bike_label_r   = r["bike_label"]
    selected_tire_r = r["selected_tire"]
    circ_mm_r  = r["circ_mm"]
    corone_r   = r["corone"]
    pignoni_r  = r["pignoni"]
    cadenza_min_r = r["cadenza_min"]
    cadenza_max_r = r["cadenza_max"]

    st.divider()
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.metric("Sviluppo min", f"{df['Sviluppo (m)'].min():.2f} m")
    with k2: st.metric("Sviluppo max", f"{df['Sviluppo (m)'].max():.2f} m")
    with k3: st.metric(f"Vel. min @{cadenza_min_r} rpm", f"{df[vmin_col].min():.1f} km/h")
    with k4: st.metric(f"Vel. max @{cadenza_max_r} rpm", f"{df[vmax_col].max():.1f} km/h")

    st.divider()
    st.subheader("Velocità")
    st.caption("Velocità raggiungibile per ogni combinazione corona/pignone, nell'intervallo di cadenza selezionato. L'area colorata rappresenta il range di velocità tra cadenza minima e massima.")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Rapporti")
    st.caption("Valore di ogni rapporto (corona/pignone) e relativo sviluppo metrico (metri percorsi per pedalata). Le barre sono ordinate dal rapporto più agile al più duro. Un salto tra un rapporto e l'altro con una variazione intorno al 5-10% è considerato ottimale. Variazioni sotto il 5% indicano una ridondanza di rapporti. Variazioni sopra il 20% determinano un salto brusco.")
    st.plotly_chart(fig2, use_container_width=True)

    if fig3 is not None:
        st.divider()
        st.subheader("Sovrapposizione dei rapporti")
        st.caption("Ogni tacca rappresenta un rapporto disponibile. Tacche vicine o sovrapposte tra corone diverse indicano rapporti ridondanti; spazi vuoti indicano salti bruschi nella progressione.")
        st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    st.subheader("Tabella rapporti")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    st.caption(f"Pneumatico: {selected_tire_r} · Circonferenza: {circ_mm_r} mm · Cadenza: {cadenza_min_r}–{cadenza_max_r} rpm")

    st.divider()

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        modello_bici = st.text_input("Modello bici", placeholder="es. Trek Domane SL6 (facoltativo)")
    with col_m2:
        modello_trasmissione = st.text_input("Modello trasmissione", placeholder="es. Shimano 105 Di2 (facoltativo)")

    if st.button("Genera report PDF", type="secondary", use_container_width=True):
        with st.spinner("Generazione PDF in corso..."):
            st.session_state.pdf_bytes = genera_pdf(
                df, df_display, fig, fig2, fig3,
                bike_label_r, selected_tire_r, circ_mm_r, corone_r, pignoni_r,
                cadenza_min_r, cadenza_max_r, vmin_col, vmax_col,
                modello_bici=modello_bici, modello_trasmissione=modello_trasmissione,
            )
        st.session_state.pdf_filename = _pdf_filename(modello_bici, modello_trasmissione)

    if st.session_state.pdf_bytes is not None:
        st.download_button(
            label="Scarica report PDF",
            data=st.session_state.pdf_bytes,
            file_name=st.session_state.get("pdf_filename", "report_trasmissione.pdf"),
            mime="application/pdf",
            use_container_width=True,
        )