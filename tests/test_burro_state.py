from src.sim.burro_state import BurroState

def test_print_burro_state_from_json():
    initial_json = {
        "initialEnergyPercent": 80,
        "healthState": "Good",
        "grassKg": 120,
        "currentAgeYears": 20,
        "deathAgeYears": 100
    }

    burro = BurroState.build_initial_burro_state_from_json(initial_json)

    print("=== BurroState construido desde JSON ===")
    print("Energía:", burro.energy_pct)
    print("Salud:", burro.health)
    print("Pasto en bodega:", burro.grass_kg)
    print("Edad actual:", burro.age_years)
    print("Vida restante:", burro.life_years_left)
    print("Nodo asignado:", burro.node)
    print("Meta:", burro.meta)
    print("========================================")
    
def test_print_burro_state_defaults():
    burro = BurroState.build_initial_burro_state_from_json({})

    print("=== BurroState con valores por defecto ===")
    print("Energía:", burro.energy_pct)
    print("Salud:", burro.health)
    print("Pasto en bodega:", burro.grass_kg)
    print("Edad actual:", burro.age_years)
    print("Vida restante:", burro.life_years_left)
    print("Nodo asignado:", burro.node)
    print("Meta:", burro.meta)
    print("==========================================")