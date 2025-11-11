from src.sim.burro_state import BurroState
from src.sim.visit import simulate_visit

def test_simulate_visit_with_print():
    # Estado inicial del burro (como si viniera del JSON)
    initial_json = {
        "initialEnergyPercent": 60,
        "healthState": "Bad",
        "grassKg": 10.0,
        "currentAgeYears": 30,
        "deathAgeYears": 100
    }

    burro = BurroState.build_initial_burro_state_from_json(initial_json)

    print("=== Estado inicial del burro ===")
    print("Energía:", burro.energy_pct)
    print("Salud:", burro.health)
    print("Pasto:", burro.grass_kg)
    print("Edad:", burro.age_years)
    print("Vida restante:", burro.life_years_left)
    print("================================")

    # Atributos de la estrella visitada
    star_attrs = {
        "id": 1,
        "label": "Estrella X",
        "time_per_kg_years": 0.2,  # puede comer 5 kg por año
        "investigation_years": 2.0,
        "invest_energy_per_year_pct": 1.0,
        "hypergiant": False
    }

    # Reglas del sistema
    rules = {
        "timeAndLife": {
            "maxFractionOfStayForEating": 0.5,
            "investigation": {
                "p_illness": 0.0,
                "p_success": 0.0
            }
        },
        "feeding": {
            "eatOnlyIfEnergyBelowPercent": 70,
            "minKgPerEat": 0.1
        },
        "energy": {
            "energyGainPerKgByHealthPercent": {
                "Excellent": 5,
                "Good": 3,
                "Bad": 2,
                "NearDeath": 1,
                "Dead": 0
            },
            "applyEnergyCap100": True
        }
    }

    # Ejecutar visita
    new_state, events = simulate_visit(burro, star_attrs, rules)

    print("\n=== Estado después de la visita ===")
    print("Energía:", new_state.energy_pct)
    print("Salud:", new_state.health)
    print("Pasto:", new_state.grass_kg)
    print("Edad:", new_state.age_years)
    print("Vida restante:", new_state.life_years_left)
    print("===================================")

    print("\nEventos registrados:")
    for e in events:
        print("-", e)