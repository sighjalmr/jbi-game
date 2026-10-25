"""Run in PIE: steps through render settings and logs an fpschart per step ("JBI bench")."""
import unreal

ES = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
WARMUP, MEASURE = 6.0, 15.0


def gw():
    return ES.get_game_world()


def cmd(c):
    unreal.SystemLibrary.execute_console_command(gw(), c)


def tree_comps():
    out = []
    for a in unreal.GameplayStatics.get_all_actors_of_class(gw(), unreal.Actor):
        out += a.get_components_by_class(unreal.InstancedSkinnedMeshComponent)
    return out


def trees(visible):
    for c in tree_comps():
        c.set_visibility(visible)


BASE = ["grass.Enable 1", "r.Skinning.DefaultAnimationMinScreenSize 0.1", "r.Shadow.Virtual.Enable 1",
        "grass.CullDistanceScale 1", "r.Shadow.Virtual.ResolutionLodBiasDirectional -0.5", "r.ScreenPercentage 100",
        "sg.GlobalIlluminationQuality 3", "sg.ShadowQuality 3", "sg.FoliageQuality 3", "sg.ReflectionQuality 3"]
OPT = BASE + ["sg.GlobalIlluminationQuality 2", "r.ScreenPercentage 75"]  # = Config/DefaultGameUserSettings.ini
STEPS = [("base", BASE, None), ("opt", OPT, None), ("base2", BASE, None), ("opt2", OPT, None)]
STEPS = globals().get("BENCH_STEPS", STEPS)

state = {"i": 0, "t": 0.0, "phase": "set", "h": None}


def tick(dt):
    if gw() is None:
        unreal.unregister_slate_post_tick_callback(state["h"])
        return
    state["t"] += dt
    name, cvars, tv = STEPS[state["i"]]
    if state["phase"] == "set":
        for c in cvars:
            cmd(c)
        if tv is not None:
            trees(tv)
        state.update(phase="warm", t=0.0)
    elif state["phase"] == "warm" and state["t"] > WARMUP:
        cmd("startfpschart")
        state.update(phase="measure", t=0.0)
    elif state["phase"] == "measure" and state["t"] > MEASURE:
        cmd("stopfpschart")
        unreal.log("JBI bench done: " + name)
        state["i"] += 1
        state.update(phase="set", t=0.0)
        if state["i"] >= len(STEPS):
            unreal.unregister_slate_post_tick_callback(state["h"])
            unreal.log("JBI bench finished")


state["h"] = unreal.register_slate_post_tick_callback(tick)
unreal.log("JBI bench started, {} steps".format(len(STEPS)))
