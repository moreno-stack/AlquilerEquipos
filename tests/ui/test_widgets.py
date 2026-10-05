"""Componentes comunes de la interfaz."""

from alquiler.ui import widgets


def test_tabla_carga_ordena_numericamente_y_devuelve_seleccion(qtbot):
    t = widgets.Tabla()
    qtbot.addWidget(t)
    t.cargar([("codigo", "Código"), ("tarifa", "Tarifa")], [
        {"id": 1, "codigo": "A", "tarifa": "$9.000", "tarifa__orden": 9000},
        {"id": 2, "codigo": "B", "tarifa": "$10.000", "tarifa__orden": 10000},
    ])
    assert t.filas_mostradas() == 2 and t.texto(0, 1) == "$9.000"
    t.sortByColumn(1, widgets.Qt.SortOrder.DescendingOrder)
    assert t.texto(0, 0) == "B"   # 10 000 > 9 000 aunque "$1…" < "$9…" como texto
    assert t.seleccionada() is None
    t.selectRow(1)
    assert t.seleccionada()["id"] == 1


def test_tabla_resalta_filas(qtbot):
    t = widgets.Tabla()
    qtbot.addWidget(t)
    t.cargar([("x", "X")], [{"x": "ok"}, {"x": "vencido"}],
             resaltar=lambda f: "peligro" if f["x"] == "vencido" else None)
    assert t.tono_fila(1) == "peligro" and t.tono_fila(0) is None


def test_insignia_cambia_texto_y_tono(qtbot):
    i = widgets.Insignia("Disponible", "ok")
    qtbot.addWidget(i)
    i.set_valor("Fuera de servicio", "peligro")
    assert (i.text(), i.tono) == ("Fuera de servicio", "peligro")


def test_tono_de_estados():
    assert widgets.tono_para("Disponible") == "ok"
    assert widgets.tono_para("Fuera de servicio") == "peligro"
    assert widgets.tono_para("vencida") == "peligro"
    assert widgets.tono_para("alta") == "ok"           # confianza alta
    assert widgets.tono_para("desconocido") == "neutro"


def test_tarjeta_resultado_muestra_estimacion_y_despliega_justificacion(qtbot):
    tarjeta = widgets.TarjetaResultado({
        "resumen": "TAL-001: puntaje ≈80/100", "confianza": "media",
        "justificacion": ["Usos 25/20 → 35 pts"], "advertencia": "Estimación basada en…",
        "indicadores": [("Usos", "25")],
    })
    qtbot.addWidget(tarjeta)
    assert "Estimación" in tarjeta.insignia_estimacion.text()
    assert "Media" in tarjeta.insignia_confianza.text()
    assert tarjeta.detalle.isHidden()
    tarjeta.boton_detalle.click()
    assert not tarjeta.detalle.isHidden()
    assert "Usos 25/20 → 35 pts" in tarjeta.detalle_texto()


def test_configurar_locale_usa_separadores_colombianos(qtbot):
    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox
    anterior = QLocale()
    try:
        widgets.configurar_locale()
        entero, decimal = QSpinBox(), QDoubleSpinBox()
        qtbot.addWidget(entero)
        qtbot.addWidget(decimal)
        entero.setRange(0, 1_000_000)
        entero.setGroupSeparatorShown(True)
        entero.setValue(40_000)
        decimal.setValue(2.5)
        assert entero.text() == "40.000" and decimal.text() == "2,50"
    finally:
        QLocale.setDefault(anterior)
