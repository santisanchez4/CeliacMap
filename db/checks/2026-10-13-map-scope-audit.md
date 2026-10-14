# Auditoría de alcance del mapa (solo lectura)

`python db/checks/map_scope_audit.py` · 2026-10-13 22:16 UTC

**No se cambió ningún estado.** Un `SELECT` paginado sobre `places` (todos los estados), sin llamadas a Google ni al modelo.
Filas leídas: 1387 (approved 417, discarded 472, needs_review 497, outreach_confirmed 1). Capa de la IM: 35 filas.

- **Seguros** (la misma regla determinista que usan los agentes): 9, de los cuales 1 están aprobados en el mapa.
- **Dudosos** (palabras sueltas, nota del Validator, giros de la IM — posibles falsos positivos): 69, de los cuales 14 están aprobados en el mapa.

## Lectura (escrita a mano sobre la salida del script)

- **Un solo aprobado cae seguro en la regla: Tienda Inglesa (Montevideo, `1aab916e`)**, en ámbar con 0,72 y sin decisión manual.
  Otras dos filas de cadenas están en la cola de revisión (Carrefour Market de La Plata, Tienda Inglesa de Punta del Este) y cuatro
  ya estaban descartadas (Géant, Carrefour Market de Mendoza, Vea, Supermercados El Dorado).
- **La Molienda (9 sucursales aprobadas) queda en dudosos y tiene decisión manual en todas:** la nota del override la describe como
  supermercado / mercado general. No se toca: es una aprobación manual. Es la decisión de fondo que deja esta auditoría: si La
  Molienda es comercio general (1a) o tienda especializada.
- **Supermercados y autoservicios independientes** (el supuesto del plan: 1a habla de cadenas): aprobados aparecen EntreSano Healthy
  Supermarket (Córdoba) y Minimarket La Isla 24 hours (Maldonado); en cola, Supermercado Betel, SUPERTIM, Family Market y La
  Florinda Market.
- **21 filas tienen como `social_url` una página de tema** (1 aprobada en 100%, La Union gluten Free Triunvirato; 7 en cola; 13
  descartadas). Casi todas son negocios reales cuyo lead salió de esa página: por eso la página de tema **no** es motivo de
  exclusión en el Validator (lo fue en el primer borrador y esta auditoría lo mostró como falso positivo). Lo que sí indica es que
  esa fila no tiene una cuenta propia cargada.
- **Falsos positivos claros entre los dudosos:** Pan del dia (la marca «Día» dentro de un nombre de panadería) y CELIDIET Mercado
  Moreno (dietética). Están listados para mostrar que la capa determinista no los excluye.
- **1b:** no hay ningún aprobado; los institutos y escuelas que aparecen ya estaban descartados. La capa de la IM no aportó ningún
  match (ninguna fila de `places` a ≤ 40 m de una habilitación de solo elaboración o distribución).

## 1. APROBADOS EN EL MAPA

### 1.1 Seguros — 1

| Lugar | Ciudad, país | Estado actual | Conf. | Motivo del match | Certeza | Decisión manual |
|---|---|---|---|---|---|---|
| Tienda Inglesa (`1aab916e`) | Montevideo, Uruguay | approved · options_available | 0.72 | 1a · cadena de comercio general (Tienda Inglesa); su oferta sin gluten varía por sucursal y no se puede verificar. | alta | no |

### 1.2 Dudosos (revisar uno por uno: pueden ser falsos positivos) — 14

| Lugar | Ciudad, país | Estado actual | Conf. | Motivo del match | Certeza | Decisión manual |
|---|---|---|---|---|---|---|
| CELIDIET Mercado Moreno (`27c9aa3b`) | Capital, Argentina | approved · celiac_friendly | 0.87 | palabra en el nombre: mercado | baja | no |
| EntreSano Healthy Supermarket (`ed42eb8d`) | Córdoba, Argentina | approved · celiac_friendly | 0.92 | la nota del Validator dice «…roducts with good variety confirming this healthy supermarket caters to celiac customers the store is a dedicated health …» | baja | no |
| La Union gluten Free Triunvirato (`b45a13a0`) | Buenos Aires, Argentina | approved · gluten_free_100 | 0.87 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/la-uni%C3%B3n-gluten-free-caballito): el lead salió de ahí | baja | no |
| Pan del dia (`a85e6f9c`) | Buenos Aires, Argentina | approved · gluten_free_100 | 0.9 | el nombre contiene la marca Día | baja | no |
| La Molienda - 18 de Julio (`16305a09`) | Montevideo, Uruguay | approved · options_available | 0.52 | la nota del Validator dice «…ns available no gluten free 100 la molienda es un supermercado mercado general huevos salsa de soja proteina cosmetica et…» | baja | sí (override) |
| La Molienda - ACJ (Colonia) (`ab09d6d4`) | Montevideo, Uruguay | approved · options_available | 0.5 | la nota del Validator dice «…ns available no gluten free 100 la molienda es un supermercado mercado general huevos salsa de soja proteina cosmetica et…» | baja | sí (override) |
| La Molienda - Carrasco (`9dd64b4e`) | Montevideo, Uruguay | approved · options_available | 0.55 | la nota del Validator dice «…ns available no gluten free 100 la molienda es un supermercado mercado general huevos salsa de soja proteina cosmetica et…» | baja | sí (override) |
| La Molienda - Costa Urbana (`59df8880`) | Ciudad de la Costa, Uruguay | approved · options_available | 0.5 | la nota del Validator dice «…ns available no gluten free 100 la molienda es un supermercado mercado general huevos salsa de soja proteina cosmetica et…» | baja | sí (override) |
| La Molienda - Ejido (`a2135458`) | Montevideo, Uruguay | approved · options_available | 0.5 | la nota del Validator dice «…ns available no gluten free 100 la molienda es un supermercado mercado general huevos salsa de soja proteina cosmetica et…» | baja | sí (override) |
| La Molienda - Parque Rodó (`b41cc805`) | Montevideo, Uruguay | approved · options_available | 0.52 | la nota del Validator dice «…ns available no gluten free 100 la molienda es un supermercado mercado general huevos salsa de soja proteina cosmetica et…» | baja | sí (override) |
| La Molienda - Punta Carretas (`3892f08f`) | Montevideo, Uruguay | approved · options_available | 0.52 | la nota del Validator dice «…ns available no gluten free 100 la molienda es un supermercado mercado general huevos salsa de soja proteina cosmetica et…» | baja | sí (override) |
| La Molienda - Sarandí (`c1199194`) | Montevideo, Uruguay | approved · options_available | 0.5 | la nota del Validator dice «…ns available no gluten free 100 la molienda es un supermercado mercado general huevos salsa de soja proteina cosmetica et…» | baja | sí (override) |
| La Molienda - Tres Cruces (`32dc14f4`) | Montevideo, Uruguay | approved · options_available | 0.52 | la nota del Validator dice «…ns available no gluten free 100 la molienda es un supermercado mercado general huevos salsa de soja proteina cosmetica et…» | baja | sí (override) |
| Minimarket La Isla 24 hours. (`22b104b1`) | Maldonado, Uruguay | approved · celiac_friendly | 0.93 | palabra en el nombre: minimarket | baja | no |

## 2. Fuera del mapa (otros estados)

### 2.1 Seguros — en cola o pendientes (`needs_review`, `pending`) — 2

| Lugar | Ciudad, país | Estado actual | Conf. | Motivo del match | Certeza | Decisión manual |
|---|---|---|---|---|---|---|
| Carrefour Market (`beb397c0`) | La Plata, Argentina | needs_review | 0.52 | 1a · cadena de comercio general (Carrefour); su oferta sin gluten varía por sucursal y no se puede verificar. | alta | no |
| Tienda Inglesa (`b735ee91`) | Punta del Este, Uruguay | needs_review | 0.52 | 1a · cadena de comercio general (Tienda Inglesa); su oferta sin gluten varía por sucursal y no se puede verificar. | alta | no |

### 2.2 Dudosos — en cola o pendientes — 15

| Lugar | Ciudad, país | Estado actual | Conf. | Motivo del match | Certeza | Decisión manual |
|---|---|---|---|---|---|---|
| CRAIG Bistró (`5ddb5c85`) | Buenos Aires, Argentina | needs_review | 0.5 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/restaurantes-sin-gluten-montevideo): el lead salió de ahí | baja | no |
| Family Market (`12e17fb2`) | Buenos Aires, Argentina | needs_review | 0.5 | palabra en el nombre: market | baja | no |
| La Florinda Market (`a11383dc`) | Ituzaingó, Argentina | needs_review | 0.52 | palabra en el nombre: market | baja | no |
| Punto Sano (`92f88609`) | Jardín América, Argentina | needs_review | 0.52 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/harina-para-celiacos-uruguay): el lead salió de ahí | baja | no |
| SUPERTIM (`efe9c89b`) | Gualeguaychú, Argentina | needs_review | 0.52 | la nota del Validator dice «…supertim parece ser un supermercado o comercio de alimentos en gualeguaychu pero la informacio…» | baja | no |
| Distrigol (`0c970e95`) | Montevideo, Uruguay | needs_review | 0.62 | la nota del Validator dice «…el nombre distrigol sugiere fuertemente una distribuidora o tienda especializada en productos sin gluten la raiz gol…» | baja | no |
| DISTRIJOMA (`a14ed2ad`) | Montevideo, Uruguay | needs_review | 0.52 | la nota del Validator dice «…el nombre distrijoma sugiere un distribuidor o mayorista de alimentos mas que un cafe y la fuente social…» | baja | no |
| Doña Marta (`170a149f`) | Montevideo, Uruguay | needs_review | 0.5 | su social_url es una página de tema, no una cuenta (https://www.facebook.com/groups/270371291453054/posts/1377484284075077): el lead salió de ahí | baja | no |
| La Cabrona MVD (`f704a851`) | Montevideo, Uruguay | needs_review | 0.5 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/la-carlote%C3%B1a-pechuga-de-pollo): el lead salió de ahí | baja | no |
| La Carola (`6cca9681`) | Montevideo, Uruguay | needs_review | 0.5 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/la-carlote%C3%B1a-pechuga-de-pollo): el lead salió de ahí | baja | no |
| Mercado Agrícola de Montevideo (`46e45082`) | Montevideo, Uruguay | needs_review | 0.52 | palabra en el nombre: mercado | baja | no |
| Mercado Uruguayo (`3aeb4619`) | Montevideo, Uruguay | needs_review | 0.52 | palabra en el nombre: mercado | baja | no |
| Norimōto (`13c7eb38`) | Montevideo, Uruguay | needs_review | 0.5 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/naccato-sushi): el lead salió de ahí | baja | no |
| Panadería Ramona Gluten Free (`f2d1034d`) | Montevideo, Uruguay | needs_review | 0.72 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/panader%C3%ADa-ramona-gluten-free-montevideo): el lead salió de ahí | baja | no |
| Supermercado Betel (`e83241f1`) | Fray Bentos, Uruguay | needs_review | 0.5 | palabra en el nombre: supermercado; la nota del Validator dice «…g razonamiento nuevo del validator se trata de un supermercado generico sin evidencia explicita de que cuente con seccion…» | baja | no |

### 2.3 Seguros — ya descartados — 6

| Lugar | Ciudad, país | Estado actual | Conf. | Motivo del match | Certeza | Decisión manual |
|---|---|---|---|---|---|---|
| Carrefour Market (`deeb1695`) | Mendoza, Argentina | discarded | 0.15 | 1a · cadena de comercio general (Carrefour); su oferta sin gluten varía por sucursal y no se puede verificar. | alta | no |
| Vea (`361a023a`) | Gualeguaychú, Argentina | discarded | 0.15 | 1a · cadena de comercio general (Vea); su oferta sin gluten varía por sucursal y no se puede verificar. | alta | no |
| Géant Fresh Market (`9f9abf53`) | Montevideo, Uruguay | discarded | 0.7 | 1a · cadena de comercio general (Géant); su oferta sin gluten varía por sucursal y no se puede verificar. | alta | no |
| Instituto Catel (`2bed94d3`) | Montevideo, Uruguay | discarded | 0.05 | 1b · el nombre indica que enseña o informa (escuela, cursos, blog o recetas); no es un local que venda o sirva al público. | alta | no |
| Instituto Savez (`0cb69c96`) | Uruguay, Uruguay | discarded | 0.95 | 1b · el nombre indica que enseña o informa (escuela, cursos, blog o recetas); no es un local que venda o sirva al público. | alta | no |
| Supermercados El Dorado (`82c2ce01`) | Fray Bentos, Uruguay | discarded | 0.15 | 1a · cadena de comercio general (El Dorado); su oferta sin gluten varía por sucursal y no se puede verificar. | alta | no |

### 2.4 Dudosos — ya descartados — 40

| Lugar | Ciudad, país | Estado actual | Conf. | Motivo del match | Certeza | Decisión manual |
|---|---|---|---|---|---|---|
| Asociación Celíaca Argentina (`ed0c06f5`) | La Plata, Argentina | discarded | 0.52 | palabra en el nombre: asociacion; la nota del Validator dice «…correccion manual 2026 09 25 no es un comercio es un evento o una organizacion no corresponde a este mapa …» | baja | no |
| Celi events (`0190a759`) | Buenos Aires, Argentina | discarded | 0.52 | la nota del Validator dice «…correccion manual 2026 09 25 no es un comercio es un evento o una organizacion no corresponde a este mapa …» | baja | no |
| Celiaco.com (`13d92e0f`) | Buenos Aires, Argentina | discarded | 0.85 | la nota del Validator dice «…tablishment despite the celiac related name it is not a restaurant cafe or shop where people with celiac disease can purchase …» | baja | no |
| ExpoCelíaca (`f1b5af9c`) | Buenos Aires, Argentina | discarded | 0.85 | la nota del Validator dice «…correccion manual 2026 09 25 no es un comercio es un evento o una organizacion no corresponde a este mapa …» | baja | no |
| Autoservicio El Ñandu (`d048a485`) | Tacuarembó, Uruguay | discarded | 0.75 | palabra en el nombre: autoservicio | baja | no |
| Bakers Industrial Center Uruguay - CIPU (`fd71ef94`) | Montevideo, Uruguay | discarded | 0.1 | la nota del Validator dice «…ipu sugiere un centro de distribucion o proveedor mayorista de insumos para panaderias no un establecimiento de venta a…» | baja | no |
| Bakery Super Chicken (`8b75c25e`) | Tacuarembó, Uruguay | discarded | 0.85 | palabra en el nombre: super | baja | no |
| Botica Del Señor (`52a3d471`) | Montevideo, Uruguay | discarded | 0.8 | la nota del Validator dice «…the name botica del senor strongly suggests a pharmacy or apothecary botica old fashioned word for pharmacy drugst…» | baja | no |
| By Gessi Cocina Inclusiva (`d6a3edb8`) | Montevideo, Uruguay | discarded | 0.82 | la nota del Validator dice «…correccion manual 2026 10 13 no es un comercio escuela de cocina de productos aptos para celiacos sin vent…» | baja | no |
| Café Brasilero (`ef8d57b5`) | Montevideo, Uruguay | discarded | 0.15 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/cafe-brasilero-montevideo): el lead salió de ahí | baja | no |
| Café Carioca, Tostadero. Fábrica, Almacén y Escuela de café (`fdae2cb4`) | Montevideo, Uruguay | discarded | 0.1 | palabra en el nombre: escuela | baja | no |
| Cecilia Méndez Alta Costura y Escuela de Moda (`0681141f`) | Punta del Este, Uruguay | discarded | 0.99 | palabra en el nombre: escuela; la nota del Validator dice «…this is a fashion design school and haute couture atelier not a food business it has no rel…» | baja | no |
| Centro de Convenciones de Punta del Este (`78eb520c`) | Punta del Este, Uruguay | discarded | 0.95 | la nota del Validator dice «…this is a convention center not a restaurant or food retail establishment it has no gluten free or celia…» | baja | no |
| Disco Groceries Store (`7316125f`) | Montevideo, Uruguay | discarded | 0.1 | el nombre contiene la marca Disco; la nota del Validator dice «…disco es una cadena de supermercados convencional de uruguay sin ninguna evidencia de especial…» | baja | no |
| Distribuidora Campofrio (`40f6e833`) | Artigas, Uruguay | discarded | 0.8 | palabra en el nombre: distribuidora | baja | no |
| El Imperio (`0eedb863`) | Montevideo, Uruguay | discarded | 0.1 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/el-imperio-montevideo): el lead salió de ahí | baja | no |
| Empieza entero (`cbbc7983`) | Montevideo, Uruguay | discarded | 0.52 | la nota del Validator dice «…correccion manual 2026 10 13 no es un comercio el agente social tomo como nombre el comienzo del texto de …» | baja | no |
| IGA Montevideo | Instituto Gastronómico de las Américas (`29962111`) | Montevideo, Uruguay | discarded | 0.1 | palabra en el nombre: instituto; la nota del Validator dice «…a celiacos la naturaleza del establecimiento como escuela de cocina representa un riesgo elevado de contaminacion cru…» | baja | no |
| KFC (`a54bf924`) | Montevideo, Uruguay | discarded | 0.05 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/kfc-montevideo): el lead salió de ahí | baja | no |
| KFC (`87e2272e`) | Montevideo, Uruguay | discarded | 0.1 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/kfc-montevideo): el lead salió de ahí | baja | no |
| La Carloteña (`efa8b719`) | Tucumán, Uruguay | discarded | 0.05 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/la-carlote%C3%B1a-pechuga-de-pollo): el lead salió de ahí | baja | no |
| Ma-pa School Crafts (`731b8c08`) | Montevideo, Uruguay | discarded | 0.05 | la nota del Validator dice «…el nombre ma pa school crafts sugiere un taller o escuela de manualidades artesani…» | baja | no |
| Maleza Beach Club (`cc81abbf`) | Punta Del Este, Uruguay | discarded | 0.15 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/maleza-beach-punta-del-este): el lead salió de ahí | baja | no |
| mercado central (`3229560a`) | Mercedes, Uruguay | discarded | 0.2 | palabra en el nombre: mercado | baja | no |
| Mercado Ferrando (`b611206c`) | Montevideo, Uruguay | discarded | 0.75 | palabra en el nombre: mercado | baja | no |
| Minimarket La Isla 24hs. Cocina y más de 1500 productos sin gluten, cerveza Patagonia y cientos de etiquetas de vino (`756d0138`) | Maldonado, Uruguay | discarded | 0.88 | palabra en el nombre: minimarket | baja | no |
| Montevideo al Sur Bar (`32910475`) | Montevideo, Uruguay | discarded | 0.15 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/montevideo-al-sur-bar): el lead salió de ahí | baja | no |
| Nippon "Authentic Asian food" (`b6806c71`) | Montevideo, Uruguay | discarded | 0.15 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/naccato-sushi): el lead salió de ahí | baja | no |
| Own Montevideo Hotel (`057bea97`) | Montevideo, Uruguay | discarded | 0.15 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/hotel-own-montevideo): el lead salió de ahí | baja | no |
| Pan Sin Gluten En Panetera (`9e6b2dd5`) | Montevideo, Uruguay | discarded | 0.52 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/pan-sin-gluten-en-panetera): el lead salió de ahí; la nota del Validator dice «…correccion manual 2026 10 13 no es un comercio la fuente es una pagina de tema de instagram no la cuenta d…» | baja | no |
| Panadería Palmar (`5cb452cf`) | Montevideo, Uruguay | discarded | 0.75 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/panaderia-palmar): el lead salió de ahí | baja | no |
| Productos Omnilife Life Revolution Abril DelgadoDistribuidor Mercantil Independiente (`9d4d9f65`) | Montevideo, Uruguay | discarded | 0.05 | la nota del Validator dice «…el lugar corresponde a un distribuidor independiente de productos omnilife una empresa de marketin…» | baja | no |
| San Francisco C.I.S.A. (`be6d68f1`) | Uruguay, Uruguay | discarded | 0.1 | su social_url es una página de tema, no una cuenta (https://www.instagram.com/popular/harina-para-celiacos-uruguay): el lead salió de ahí; la nota del Validator dice «… y la direccion sugieren una empresa industrial o distribuidora c i s a es una sigla corporativa sin ninguna referencia a …» | baja | no |
| Sattva Uniformes (`c412985c`) | Montevideo, Uruguay | discarded | 0.02 | su social_url es una página de tema, no una cuenta (https://www.facebook.com/groups/1040492759367133/posts/1458275460922192): el lead salió de ahí | baja | no |
| Serendipia-cea (`d9fd1d57`) | Montevideo, Uruguay | discarded | 0.88 | la nota del Validator dice «…omico el social agent lo tomo de un post de un concurso de cocina interno serendichef y el validator lo aprobo como…» | baja | sí (override) |
| SuChina S.A - Distribuidor Mayorista (`7fbdc915`) | Montevideo, Uruguay | discarded | 0.1 | palabra en el nombre: mayorista, distribuidor; la nota del Validator dice «…no existe evidencia alguna de que este distribuidor mayorista ofrezca productos sin tacc o gluten free el nombr…» | baja | no |
| Super USA (`43f81096`) | Colonia del Sacramento, Uruguay | discarded | 0.8 | palabra en el nombre: super; la nota del Validator dice «…super usa appears to be a generic supermarket with no gluten free or celiac specific signals in its name …» | baja | no |
| Supermercado Giordano (`552b9529`) | Durazno, Uruguay | discarded | 0.1 | palabra en el nombre: supermercado; la nota del Validator dice «…o se encontro ninguna evidencia especifica de que supermercado giordano ofrezca productos o secciones dedicadas a celiaco…» | baja | no |
| Supermercado La Familiar (`0a48afe8`) | Fray Bentos, Uruguay | discarded | 0.1 | palabra en el nombre: supermercado; la nota del Validator dice «… validator no se encontro evidencia alguna de que supermercado la familiar ofrezca productos o secciones dedicadas sin ta…» | baja | no |
| Terminal Tres Cruces (`499459cd`) | Montevideo, Uruguay | discarded | 0.95 | la nota del Validator dice «…tres cruces is a major bus terminal in montevideo not a restaurant or food establishment it is not a gluten free or celiac spe…» | baja | no |
