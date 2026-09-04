from __future__ import annotations


ANSWER_OPTIONS = (
    ("A", "Siempre", 1),
    ("B", "Casi siempre", 2),
    ("C", "Algunas veces", 3),
    ("D", "Casi nunca", 4),
    ("E", "Nunca", 5),
)

# Official wording for Forma A. The application stores raw positions (1-5), not
# transformed risk scores; scoring depends on the instrument's professional rules.
QUESTION_TEXTS: dict[int, str] = {
    1: "El ruido en el lugar donde trabajo es molesto",
    2: "En el lugar donde trabajo hace mucho frío",
    3: "En el lugar donde trabajo hace mucho calor",
    4: "El aire en el lugar donde trabajo es fresco y agradable",
    5: "La luz del sitio donde trabajo es agradable",
    6: "El espacio donde trabajo es cómodo",
    7: "En mi trabajo me preocupa estar expuesto a sustancias químicas que afecten mi salud",
    8: "Mi trabajo me exige hacer mucho esfuerzo físico",
    9: "Los equipos o herramientas con los que trabajo son cómodos",
    10: (
        "En mi trabajo me preocupa estar expuesto a microbios, animales o plantas "
        "que afecten mi salud"
    ),
    11: "Me preocupa accidentarme en mi trabajo",
    12: "El lugar donde trabajo es limpio y ordenado",
    13: "Por la cantidad de trabajo que tengo debo quedarme tiempo adicional",
    14: "Me alcanza el tiempo de trabajo para tener al día mis deberes",
    15: "Por la cantidad de trabajo que tengo debo trabajar sin parar",
    16: "Mi trabajo me exige hacer mucho esfuerzo mental",
    17: "Mi trabajo me exige estar muy concentrado",
    18: "Mi trabajo me exige memorizar mucha información",
    19: "En mi trabajo tengo que tomar decisiones difíciles muy rápido",
    20: "Mi trabajo me exige atender a muchos asuntos al mismo tiempo",
    21: "Mi trabajo requiere que me fije en pequeños detalles",
    22: "En mi trabajo respondo por cosas de mucho valor",
    23: "En mi trabajo respondo por dinero de la empresa",
    24: "Como parte de mis funciones debo responder por la seguridad de otros",
    25: "Respondo ante mi jefe por los resultados de toda mi área de trabajo",
    26: "Mi trabajo me exige cuidar la salud de otras personas",
    27: "En el trabajo me dan órdenes contradictorias",
    28: "En mi trabajo me piden hacer cosas innecesarias",
    29: (
        "En mi trabajo se presentan situaciones en las que debo pasar por alto normas "
        "o procedimientos"
    ),
    30: "En mi trabajo tengo que hacer cosas que se podrían hacer de una forma más práctica",
    31: "Trabajo en horario de noche",
    32: "En mi trabajo es posible tomar pausas para descansar",
    33: "Mi trabajo me exige laborar en días de descanso, festivos o fines de semana",
    34: "En mi trabajo puedo tomar fines de semana o días de descanso al mes",
    35: "Cuando estoy en casa sigo pensando en el trabajo",
    36: "Discuto con mi familia o amigos por causa de mi trabajo",
    37: "Debo atender asuntos de trabajo cuando estoy en casa",
    38: "Por mi trabajo el tiempo que paso con mi familia y amigos es muy poco",
    39: "Mi trabajo me permite desarrollar mis habilidades",
    40: "Mi trabajo me permite aplicar mis conocimientos",
    41: "Mi trabajo me permite aprender nuevas cosas",
    42: "Me asignan el trabajo teniendo en cuenta mis capacidades",
    43: "Puedo tomar pausas cuando las necesito",
    44: "Puedo decidir cuánto trabajo hago en el día",
    45: "Puedo decidir la velocidad a la que trabajo",
    46: "Puedo cambiar el orden de las actividades en mi trabajo",
    47: "Puedo parar un momento mi trabajo para atender algún asunto personal",
    48: "Los cambios en mi trabajo han sido beneficiosos",
    49: "Me explican claramente los cambios que ocurren en mi trabajo",
    50: "Puedo dar sugerencias sobre los cambios que ocurren en mi trabajo",
    51: "Cuando se presentan cambios en mi trabajo se tienen en cuenta mis ideas y sugerencias",
    52: "Los cambios que se presentan en mi trabajo dificultan mi labor",
    53: "Me informan con claridad cuáles son mis funciones",
    54: "Me informan cuáles son las decisiones que puedo tomar en mi trabajo",
    55: "Me explican claramente los resultados que debo lograr en mi trabajo",
    56: "Me explican claramente el efecto de mi trabajo en la empresa",
    57: "Me explican claramente los objetivos de mi trabajo",
    58: "Me informan claramente quién me puede orientar para hacer mi trabajo",
    59: "Me informan claramente con quién puedo resolver los asuntos de trabajo",
    60: "La empresa me permite asistir a capacitaciones relacionadas con mi trabajo",
    61: "Recibo capacitación útil para hacer mi trabajo",
    62: "Recibo capacitación que me ayuda a hacer mejor mi trabajo",
    63: "Mi jefe me da instrucciones claras",
    64: "Mi jefe ayuda a organizar mejor el trabajo",
    65: "Mi jefe tiene en cuenta mis puntos de vista y opiniones",
    66: "Mi jefe me anima para hacer mejor mi trabajo",
    67: "Mi jefe distribuye las tareas de forma que me facilita el trabajo",
    68: "Mi jefe me comunica a tiempo la información relacionada con el trabajo",
    69: "La orientación que me da mi jefe me ayuda a hacer mejor el trabajo",
    70: "Mi jefe me ayuda a progresar en el trabajo",
    71: "Mi jefe me ayuda a sentirme bien en el trabajo",
    72: "Mi jefe ayuda a solucionar los problemas que se presentan en el trabajo",
    73: "Siento que puedo confiar en mi jefe",
    74: "Mi jefe me escucha cuando tengo problemas de trabajo",
    75: "Mi jefe me brinda su apoyo cuando lo necesito",
    76: "Me agrada el ambiente de mi grupo de trabajo",
    77: "En mi grupo de trabajo me tratan de forma respetuosa",
    78: "Siento que puedo confiar en mis compañeros de trabajo",
    79: "Me siento a gusto con mis compañeros de trabajo",
    80: "En mi grupo de trabajo algunas personas me maltratan",
    81: "Entre compañeros solucionamos los problemas de forma respetuosa",
    82: "Hay integración en mi grupo de trabajo",
    83: "Mi grupo de trabajo es muy unido",
    84: "Las personas en mi trabajo me hacen sentir parte del grupo",
    85: "Cuando tenemos que realizar trabajo de grupo los compañeros colaboran",
    86: "Es fácil poner de acuerdo al grupo para hacer el trabajo",
    87: "Mis compañeros de trabajo me ayudan cuando tengo dificultades",
    88: "En mi trabajo las personas nos apoyamos unos a otros",
    89: "Algunos compañeros de trabajo me escuchan cuando tengo problemas",
    90: "Me informan sobre lo que hago bien en mi trabajo",
    91: "Me informan sobre lo que debo mejorar en mi trabajo",
    92: "La información que recibo sobre mi rendimiento en el trabajo es clara",
    93: "La forma como evalúan mi trabajo en la empresa me ayuda a mejorar",
    94: "Me informan a tiempo sobre lo que debo mejorar en el trabajo",
    95: "En la empresa confían en mi trabajo",
    96: "En la empresa me pagan a tiempo mi salario",
    97: "El pago que recibo es el que me ofreció la empresa",
    98: "El pago que recibo es el que merezco por el trabajo que realizo",
    99: "En mi trabajo tengo posibilidades de progresar",
    100: "Las personas que hacen bien el trabajo pueden progresar en la empresa",
    101: "La empresa se preocupa por el bienestar de los trabajadores",
    102: "Mi trabajo en la empresa es estable",
    103: "El trabajo que hago me hace sentir bien",
    104: "Siento orgullo de trabajar en esta empresa",
    105: "Hablo bien de la empresa con otras personas",
    106: "Atiendo clientes o usuarios muy enojados",
    107: "Atiendo clientes o usuarios muy preocupados",
    108: "Atiendo clientes o usuarios muy tristes",
    109: "Mi trabajo me exige atender personas muy enfermas",
    110: "Mi trabajo me exige atender personas muy necesitadas de ayuda",
    111: "Atiendo clientes o usuarios que me maltratan",
    112: "Para hacer mi trabajo debo demostrar sentimientos distintos a los míos",
    113: "Mi trabajo me exige atender situaciones de violencia",
    114: "Mi trabajo me exige atender situaciones muy tristes o dolorosas",
    115: "Tengo colaboradores que comunican tarde los asuntos de trabajo",
    116: "Tengo colaboradores que tienen comportamientos irrespetuosos",
    117: "Tengo colaboradores que dificultan la organización del trabajo",
    118: "Tengo colaboradores que guardan silencio cuando les piden opiniones",
    119: "Tengo colaboradores que dificultan el logro de los resultados del trabajo",
    120: "Tengo colaboradores que expresan de forma irrespetuosa sus desacuerdos",
    121: "Tengo colaboradores que cooperan poco cuando se necesita",
    122: "Tengo colaboradores que me preocupan por su desempeño",
    123: "Tengo colaboradores que ignoran las sugerencias para mejorar su trabajo",
}


def expected_question_numbers(
    serves_customers: bool | None, is_manager: bool | None
) -> set[int]:
    expected = set(range(1, 106))
    if serves_customers is not False:
        expected.update(range(106, 115))
    if is_manager is not False:
        expected.update(range(115, 124))
    return expected


def applicability(
    question_number: int, serves_customers: bool | None, is_manager: bool | None
) -> str:
    if 106 <= question_number <= 114 and serves_customers is False:
        return "not_applicable"
    if 115 <= question_number <= 123 and is_manager is False:
        return "not_applicable"
    return "expected"
