# ¿Quedaron instalados los módulos que se pidieron? La pregunta se le hace a la
# base y no al código de salida de Odoo. Un `-i` puede terminar bien y dejar
# módulos fuera: si uno revienta al cargar sus datos, los que dependen de él se
# quedan atrás, y la corrida siguiente —la de las pruebas— arranca igual, con
# menos módulos de los que cree.
#
# La lista llega escrita arriba, en PEDIDOS, desde ci/pruebas.sh, y `env` lo pone
# `odoo shell`: el linter no puede ver ninguno de los dos, por eso llevan noqa.
# La respuesta es una línea «R instalados: ...» que el guion exige leer: si esta
# comprobación no llega a imprimirla, la batería falla igual. Va con print y no
# con el logger porque la corrida usa --log-level=error y el logger se la tragaría.
# pylint: disable=print-used
pedidos = [nombre for nombre in PEDIDOS.split(",") if nombre]  # noqa: F821
modulos = env["ir.module.module"].search([("name", "in", pedidos)])  # noqa: F821
estado = {m.name: m.state for m in modulos}
faltan = [
    (nombre, estado.get(nombre, "no existe"))
    for nombre in pedidos
    if estado.get(nombre) != "installed"
]
if faltan:
    detalle = ", ".join(f"{nombre} ({situacion})" for nombre, situacion in faltan)
    print(f"R instalados: faltan {detalle}")
else:
    print(f"R instalados: {len(pedidos)} de {len(pedidos)}")
