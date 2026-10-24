#include "MapDataSpawner.h"

#include "GrindRail.h"
#include "Components/SplineComponent.h"
#include "Dom/JsonObject.h"
#include "EngineUtils.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

const FName AMapDataSpawner::RailTag(TEXT("JBI_MapRail"));

AMapDataSpawner::AMapDataSpawner()
{
	PrimaryActorTick.bCanEverTick = false;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
}

FVector AMapDataSpawner::ToWorld(double East, double North, float HeightAboveGround) const
{
	const FVector XY(East * 100.0, -North * 100.0, 0.0);
	FHitResult Hit;
	FCollisionQueryParams Params(SCENE_QUERY_STAT(JBIMapTrace), false);
	const bool bHit = GetWorld()->LineTraceSingleByChannel(Hit, XY + FVector(0, 0, 100000.0), XY - FVector(0, 0, 100000.0), ECC_Visibility, Params);
	const double Ground = bHit ? Hit.ImpactPoint.Z : 0.0;
	return FVector(XY.X, XY.Y, Ground + HeightAboveGround);
}

AGrindRail* AMapDataSpawner::MakeRail(const TArray<FVector>& Points, FName GrindName, float Thickness)
{
	if (Points.Num() < 2)
	{
		return nullptr;
	}
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	AGrindRail* Rail = GetWorld()->SpawnActor<AGrindRail>(AGrindRail::StaticClass(), FTransform(Points[0]), Params);
	if (!Rail)
	{
		return nullptr;
	}
	Rail->Tags.Add(RailTag);
	Rail->GrindName = GrindName;
	Rail->RailThickness = Thickness;
	Rail->SetPoints(Points);
#if WITH_EDITOR
	Rail->SetFolderPath(TEXT("MapRails"));
#endif
	return Rail;
}

int32 AMapDataSpawner::SpawnFromFile(const FString& File, TFunctionRef<void(const TSharedPtr<FJsonObject>&, const TSharedPtr<FJsonObject>&)> Visit)
{
	const FString Path = FPaths::Combine(FPaths::ProjectDir(), GeoJsonDir, File);
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *Path))
	{
		UE_LOG(LogTemp, Error, TEXT("JBI map: cannot read %s"), *Path);
		return 0;
	}
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
	{
		UE_LOG(LogTemp, Error, TEXT("JBI map: bad JSON in %s"), *Path);
		return 0;
	}
	int32 Count = 0;
	for (const TSharedPtr<FJsonValue>& Value : Root->GetArrayField(TEXT("features")))
	{
		const TSharedPtr<FJsonObject> Feature = Value->AsObject();
		if (Feature.IsValid())
		{
			Visit(Feature->GetObjectField(TEXT("properties")), Feature->GetObjectField(TEXT("geometry")));
			++Count;
		}
	}
	return Count;
}

static TArray<FVector2D> ReadLine(const TSharedPtr<FJsonObject>& Geometry)
{
	TArray<FVector2D> Out;
	if (Geometry->GetStringField(TEXT("type")) != TEXT("LineString"))
	{
		return Out;
	}
	for (const TSharedPtr<FJsonValue>& P : Geometry->GetArrayField(TEXT("coordinates")))
	{
		const TArray<TSharedPtr<FJsonValue>>& XY = P->AsArray();
		Out.Emplace(XY[0]->AsNumber(), XY[1]->AsNumber());
	}
	return Out;
}

static double LineLength(const TArray<FVector2D>& Line)
{
	double Len = 0.0;
	for (int32 i = 1; i < Line.Num(); ++i)
	{
		Len += FVector2D::Distance(Line[i - 1], Line[i]);
	}
	return Len;
}

void AMapDataSpawner::SpawnRails()
{
	ClearRails();
	int32 Stairs = 0, Benches = 0, Ledges = 0;

	auto LineRail = [this](const TArray<FVector2D>& Line, float Height, FName Name, float Thickness)
	{
		TArray<FVector> Points;
		for (const FVector2D& P : Line)
		{
			Points.Add(ToWorld(P.X, P.Y, Height));
		}
		return MakeRail(Points, Name, Thickness) != nullptr;
	};

	if (bStairHandrails)
	{
		SpawnFromFile(TEXT("roads.geojson"), [&](const TSharedPtr<FJsonObject>& Props, const TSharedPtr<FJsonObject>& Geometry)
		{
			FString Class;
			if (Props->TryGetStringField(TEXT("class"), Class) && Class == TEXT("steps"))
			{
				const TArray<FVector2D> Line = ReadLine(Geometry);
				if (Line.Num() >= 2 && LineLength(Line) >= 2.0 && LineRail(Line, HandrailHeight, TEXT("Handrail Grind"), 6.f))
				{
					++Stairs;
				}
			}
		});
	}

	SpawnFromFile(TEXT("street_props.geojson"), [&](const TSharedPtr<FJsonObject>& Props, const TSharedPtr<FJsonObject>& Geometry)
	{
		FString Class;
		if (!Props->TryGetStringField(TEXT("class"), Class))
		{
			return;
		}
		const FString Type = Geometry->GetStringField(TEXT("type"));
		if (bBenches && Class == TEXT("bench") && Type == TEXT("Point"))
		{
			const TArray<TSharedPtr<FJsonValue>>& XY = Geometry->GetArrayField(TEXT("coordinates"));
			const FVector2D C(XY[0]->AsNumber(), XY[1]->AsNumber());
			// No orientation in the data: pick a stable pseudo-random one so re-spawning gives the same layout.
			const double Yaw = FMath::Frac(FMath::Sin(C.X * 12.9898 + C.Y * 78.233) * 43758.5453) * PI;
			const FVector2D Half(FMath::Cos(Yaw) * 0.9, FMath::Sin(Yaw) * 0.9);
			if (LineRail({ C - Half, C + Half }, BenchHeight, TEXT("Bench Slide"), 12.f))
			{
				++Benches;
			}
		}
		else if (bWallsAndGuardRails && (Class == TEXT("wall") || Class == TEXT("retaining_wall") || Class == TEXT("guard_rail") || Class == TEXT("kerb")))
		{
			const TArray<FVector2D> Line = ReadLine(Geometry);
			if (Line.Num() < 2 || LineLength(Line) > MaxLedgeLength)
			{
				return;
			}
			const bool bCurb = Class == TEXT("kerb");
			const FName Name = Class == TEXT("guard_rail") ? FName(TEXT("Rail Grind")) : (bCurb ? FName(TEXT("Curb Slide")) : FName(TEXT("Ledge Grind")));
			if (LineRail(Line, bCurb ? 15.f : LedgeHeight, Name, bCurb ? 10.f : 14.f))
			{
				++Ledges;
			}
		}
	});

	UE_LOG(LogTemp, Display, TEXT("JBI map: spawned %d stair handrails, %d benches, %d ledges/rails"), Stairs, Benches, Ledges);
}

void AMapDataSpawner::ClearRails()
{
	TArray<AActor*> ToDestroy;
	for (AGrindRail* Rail : TActorRange<AGrindRail>(GetWorld()))
	{
		if (Rail->Tags.Contains(RailTag))
		{
			ToDestroy.Add(Rail);
		}
	}
	for (AActor* A : ToDestroy)
	{
		A->Destroy();
	}
}
