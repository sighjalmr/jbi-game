# ЖБИ

Открытый мир района ЖБИ (Екатеринбург) на Unreal Engine 5.8: жизнь на районе в духе Bully, скейт и BMX в духе Tony Hawk. Карта собрана из реальных данных: OpenStreetMap, Overture Maps и рельеф Copernicus.

Дизайн-документ: [ЖБИ: дизайн-документ игры](https://claude.ai/artifact/UrmWLvWWpAkp7WKrFateiW)

## Что уже есть

- **Скейт и BMX** (`USkateMovementComponent`): накат с инерцией, повороты «карвингом», ускорение под горку, торможение.
- **Грайнд** (`AGrindRail`): запрыгиваешь сверху на рельс, и персонаж едет по сплайну. С рельса можно спрыгнуть олли.
- **Трюки и комбо** (`UTrickComponent`): олли, флипы, грэбы, вращения 180/360, очки = база × множитель. Если приземлиться посреди флипа, будет падение и комбо сгорит.
- **Реальные споты** (`AMapDataSpawner`): перила на лестницах, лавки, парапеты и отбойники ЖБИ ставятся из данных карты одной кнопкой.
- **HUD** со счётом, скоростью и текущим комбо.
- **Данные карты** в `MapData/`: рельеф 4×4 км, 5038 зданий, дороги, маски покраски.

Персонаж пока цилиндр с доской-кубом: анимаций и моделей ещё нет.

## Первый запуск

Нужны: Unreal Engine 5.8.4, Visual Studio 2022 с «Game development with C++», [Git LFS](https://git-lfs.com).

1. `git lfs install`, затем клонируй репозиторий.
2. Правый клик по `JBI.uproject` → **Generate Visual Studio project files**.
3. Открой `JBI.sln`, конфигурация **Development Editor**, собери (Ctrl+Shift+B). Или просто открой `JBI.uproject`: движок сам предложит собрать модуль.

## Уровень ЖБИ

Уровень лежит в `Content/JBI/Maps/JBI_World` и открывается при запуске редактора и игры (ассеты уровня хранятся в Git LFS). В нём рельеф, здания, дороги, свет, 285 рельсов для грайнда и точка старта у лестниц на Высоцкого.

Если нужно собрать его заново:

1. **File → New Level → Empty Open World**, сохрани как `Content/JBI/Maps/JBI_World`.
2. **Ландшафт**: Landscape Mode → Manage → Import from File → `MapData/heightmap/jbi_heightmap_2017.png`.
   - World Partition Region Size `32`. С меньшим значением Unreal 5.8 повторяет первый кусок рельефа по всей карте.
   - Section Size 63×63, Sections per Component 1×1, Components 32×32.
   - Location: X `0`, Y `0`, Z `6507.57` (Unreal ставит ландшафт центром в эту точку).
   - Scale: X `200`, Y `200`, Z `25.4202`.
   - Есть и подробная версия `jbi_heightmap_4033.png` (Scale X/Y `100`, Components 64×64, Region Size 64), но на средней видеокарте редактор с ней падает.
3. **Здания и дороги**: Tools → Execute Python Script → `Tools/ue/import_map_meshes.py`. Скрипт импортирует все `.glb` и ставит их в (0,0,0). В Static Mesh каждого тайла поставь Collision Complexity = Use Complex Collision As Simple, иначе коллизия будет коробкой на весь квартал.
4. **Проверка совмещения**: красные столбы (`alignment_markers`) должны стоять в углах ландшафта. Если меши импортированы до исправления осей, поверни их все на −90° по Z.
5. **Небо и свет**: Window → Env. Light Mixer → создай Sky Light, Directional Light, Sky Atmosphere, Height Fog. Height Fog поставь на высоту Z ≈ 9000, иначе карта утонет в тумане.
6. **Рельсы**: перетащи в уровень `MapDataSpawner` (Place Actors → All Classes) и нажми **Spawn Rails** в Details.
7. **Внешний вид**: `python3 Tools/art/gen_facades.py MapData/textures` и `python3 Tools/art/gen_ground.py MapData/textures` рисуют текстуры фасадов и земли. Затем в Unreal выполни `Tools/ue/apply_city_look.py` (материалы, здания с фасадами, дороги) и `Tools/ue/landscape_material.py` (покраска рельефа по маскам района). Детальные здания (цоколь, парапет, машинные помещения на крышах, разные оттенки) собирает `python3 Tools/map/build_buildings.py MapData`, в Unreal их заменяет `Tools/ue/apply_buildings.py`.
8. **Старт**: поставь Player Start у лестниц на Высоцкого (X ≈ -23000, Y ≈ -131200, Z ≈ 11400). Жми Play.

## Управление

| Действие | Клавиатура | Геймпад |
|---|---|---|
| Ходьба / толчок и поворот | WASD | левый стик |
| Камера | мышь | правый стик |
| Олли / прыжок | Пробел | A |
| Тормоз | Shift или S | B |
| Скейт вкл/выкл | F | Y |
| BMX вкл/выкл | B | D-pad вверх |
| Kickflip / Barspin | J | X |
| Heelflip / Tailwhip | K | RB |
| Shove-it / X-Up | L | LB |
| Grab / Superman | I | RT |
| Вращение в воздухе | A / D | левый стик |

Грайнд включается сам, когда падаешь на рельс сверху.

## Структура

| Путь | Что |
|---|---|
| `Source/JBI/` | C++ код игры |
| `Config/` | Настройки проекта (GameMode, Enhanced Input, рендер) |
| `MapData/` | Данные карты, не ассеты движка. Описание в `MapData/README.md` |
| `Tools/map/` | Python-скрипты, которые собирают `MapData` из Overture Maps и Copernicus |
| `Tools/ue/` | Скрипты для редактора Unreal |

Ассеты (`.uasset`, `.umap`) хранятся в Git LFS, см. `.gitattributes`.

## Лицензии данных

Здания, дороги, POI: © OpenStreetMap contributors (ODbL), Overture Maps Foundation, Microsoft Building Footprints (ODbL). Рельеф: Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA. Эти строки должны быть в титрах игры.
