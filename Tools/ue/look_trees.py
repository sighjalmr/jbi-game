"""Editor helper: load every World Partition actor and put the viewport camera at the edge of a wood."""
import unreal

WPL = unreal.WorldPartitionBlueprintLibrary
WPL.load_actors([d.guid for d in WPL.get_actor_descs()])

trees = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
         if str(a.get_folder_path()).startswith("Trees")]
comps = [c for a in trees for c in a.get_components_by_class(unreal.InstancedSkinnedMeshComponent)]
count = sum(c.get_instance_count() for c in comps) if hasattr(unreal.InstancedSkinnedMeshComponent, "get_instance_count") else len(comps)
unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(
    unreal.Vector(98000, 135000, 10800), unreal.Rotator(0, -8, 5))
unreal.log("JBI look: {} tree actors, {} trees".format(len(trees), count))
