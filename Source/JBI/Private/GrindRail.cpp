#include "GrindRail.h"

#include "Components/SplineComponent.h"
#include "Components/SplineMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

AGrindRail::AGrindRail()
{
	PrimaryActorTick.bCanEverTick = false;

	Spline = CreateDefaultSubobject<USplineComponent>(TEXT("Spline"));
	SetRootComponent(Spline);

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	if (Cylinder.Succeeded())
	{
		RailMesh = Cylinder.Object;
	}
}

void AGrindRail::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	RebuildMeshes();
}

void AGrindRail::SetPoints(const TArray<FVector>& WorldPoints)
{
	Spline->SetSplinePoints(WorldPoints, ESplineCoordinateSpace::World, true);
	for (int32 i = 0; i < Spline->GetNumberOfSplinePoints(); ++i)
	{
		Spline->SetSplinePointType(i, ESplinePointType::Linear, false);
	}
	Spline->UpdateSpline();
	RebuildMeshes();
}

bool AGrindRail::FindClosest(const FVector& Location, FVector& OutPoint, float& OutDistance) const
{
	if (Spline->GetNumberOfSplinePoints() < 2)
	{
		return false;
	}
	const float Key = Spline->FindInputKeyClosestToWorldLocation(Location);
	OutPoint = Spline->GetLocationAtSplineInputKey(Key, ESplineCoordinateSpace::World);
	OutDistance = Spline->GetDistanceAlongSplineAtSplineInputKey(Key);
	return true;
}

void AGrindRail::RebuildMeshes()
{
	TArray<USplineMeshComponent*> Old;
	GetComponents(Old);
	for (USplineMeshComponent* C : Old)
	{
		C->DestroyComponent();
	}
	if (!RailMesh)
	{
		return;
	}

	// Engine cylinder is 100 cm tall along Z and 100 cm wide.
	const float Scale = RailThickness / 100.f;
	for (int32 i = 0; i < Spline->GetNumberOfSplinePoints() - 1; ++i)
	{
		USplineMeshComponent* Seg = NewObject<USplineMeshComponent>(this);
		// Rebuilt by OnConstruction on every load/edit, so it is not saved with the level.
		Seg->CreationMethod = EComponentCreationMethod::UserConstructionScript;
		Seg->SetMobility(EComponentMobility::Movable);
		Seg->SetStaticMesh(RailMesh);
		Seg->SetForwardAxis(ESplineMeshAxis::Z, false);
		Seg->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Seg->SetStartScale(FVector2D(Scale, Scale), false);
		Seg->SetEndScale(FVector2D(Scale, Scale), false);
		const FVector P0 = Spline->GetLocationAtSplinePoint(i, ESplineCoordinateSpace::Local);
		const FVector P1 = Spline->GetLocationAtSplinePoint(i + 1, ESplineCoordinateSpace::Local);
		Seg->SetStartAndEnd(P0, P1 - P0, P1, P1 - P0, false);
		Seg->SetupAttachment(Spline);
		Seg->RegisterComponent();
		Seg->UpdateMesh();
	}
}
