#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GrindRail.generated.h"

class USplineComponent;
class UStaticMesh;

/** Anything you can grind on: handrails, benches, ledges, curbs. The spline is the grind line. */
UCLASS()
class JBI_API AGrindRail : public AActor
{
	GENERATED_BODY()

public:
	AGrindRail();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Grind")
	TObjectPtr<USplineComponent> Spline;

	/** Mesh stretched along the spline so the rail is visible. Defaults to the engine cylinder. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grind")
	TObjectPtr<UStaticMesh> RailMesh;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grind")
	float RailThickness = 6.f;

	/** Trick name shown when the grind starts, e.g. "50-50" or "Bench Slide". */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Grind")
	FName GrindName = TEXT("50-50");

	/** Replace the spline with these world-space points and rebuild the visible mesh. */
	UFUNCTION(BlueprintCallable, Category = "Grind")
	void SetPoints(const TArray<FVector>& WorldPoints);

	/** Closest point on the rail to Location, with the distance along the spline. */
	bool FindClosest(const FVector& Location, FVector& OutPoint, float& OutDistance) const;

	virtual void OnConstruction(const FTransform& Transform) override;

private:
	void RebuildMeshes();
};
