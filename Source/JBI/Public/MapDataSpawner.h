#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MapDataSpawner.generated.h"

class AGrindRail;
class FJsonObject;

/**
 * Drop one into the level, then press "Spawn Rails" in the Details panel.
 * Reads MapData/geojson (real JBI district data) and places grind rails on real stairs, benches, walls and guard rails.
 *
 * GeoJSON coordinates are metres from the map centre, X = east, Y = north.
 * In Unreal that is X = east, Y = south (left-handed), in centimetres, same as the landscape import.
 */
UCLASS()
class JBI_API AMapDataSpawner : public AActor
{
	GENERATED_BODY()

public:
	AMapDataSpawner();

	UFUNCTION(CallInEditor, BlueprintCallable, Category = "JBI Map")
	void SpawnRails();

	UFUNCTION(CallInEditor, BlueprintCallable, Category = "JBI Map")
	void ClearRails();

	UPROPERTY(EditAnywhere, Category = "JBI Map")
	bool bStairHandrails = true;

	UPROPERTY(EditAnywhere, Category = "JBI Map")
	bool bBenches = true;

	UPROPERTY(EditAnywhere, Category = "JBI Map")
	bool bWallsAndGuardRails = true;

	/** Skip walls longer than this, they are usually fences along roads. */
	UPROPERTY(EditAnywhere, Category = "JBI Map", meta = (Units = "m"))
	float MaxLedgeLength = 120.f;

	UPROPERTY(EditAnywhere, Category = "JBI Map", meta = (Units = "cm"))
	float HandrailHeight = 90.f;

	UPROPERTY(EditAnywhere, Category = "JBI Map", meta = (Units = "cm"))
	float BenchHeight = 45.f;

	UPROPERTY(EditAnywhere, Category = "JBI Map", meta = (Units = "cm"))
	float LedgeHeight = 55.f;

	/** Folder under the project root with the geojson files. */
	UPROPERTY(EditAnywhere, Category = "JBI Map")
	FString GeoJsonDir = TEXT("MapData/geojson");

private:
	static const FName RailTag;

	FVector ToWorld(double East, double North, float HeightAboveGround) const;
	AGrindRail* MakeRail(const TArray<FVector>& Points, FName GrindName, float Thickness);
	int32 SpawnFromFile(const FString& File, TFunctionRef<void(const TSharedPtr<FJsonObject>&, const TSharedPtr<FJsonObject>&)> Visit);
};
