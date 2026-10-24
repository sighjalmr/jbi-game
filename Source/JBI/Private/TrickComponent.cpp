#include "TrickComponent.h"

UTrickComponent::UTrickComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
}

void UTrickComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
	FlipTimeLeft = FMath::Max(0.f, FlipTimeLeft - DeltaTime);
}

bool UTrickComponent::StartAirTrick(FName Name, int32 Points, float Duration)
{
	if (IsFlipping())
	{
		return false;
	}
	FlipTimeLeft = Duration;
	AddTrick(Name, Points);
	return true;
}

void UTrickComponent::AddTrick(FName Name, int32 Points)
{
	ComboBase += Points;
	++Multiplier;
	// Same trick twice in a row only extends the line, it doesn't spam the HUD.
	if (ComboNames.Num() == 0 || ComboNames.Last() != Name)
	{
		ComboNames.Add(Name);
	}
}

void UTrickComponent::AddBalanceTime(float DeltaSeconds)
{
	BalanceRemainder += BalancePointsPerSecond * DeltaSeconds;
	const int32 Whole = FMath::FloorToInt(BalanceRemainder);
	ComboBase += Whole;
	BalanceRemainder -= Whole;
}

void UTrickComponent::Land()
{
	if (IsFlipping())
	{
		Bail();
		return;
	}
	if (!IsInCombo())
	{
		return;
	}
	LastBanked = ComboBase * Multiplier;
	TotalScore += LastBanked;
	OnComboBanked.Broadcast(LastBanked, TotalScore);
	ResetCombo();
}

void UTrickComponent::Bail()
{
	LastBanked = 0;
	ResetCombo();
	OnBail.Broadcast();
}

void UTrickComponent::ResetCombo()
{
	ComboBase = 0;
	Multiplier = 0;
	FlipTimeLeft = 0.f;
	BalanceRemainder = 0.f;
	ComboNames.Reset();
}

FString UTrickComponent::GetComboText() const
{
	if (!IsInCombo())
	{
		return FString();
	}
	TArray<FString> Parts;
	for (const FName& N : ComboNames)
	{
		Parts.Add(N.ToString());
	}
	return FString::Printf(TEXT("%s   %d x %d"), *FString::Join(Parts, TEXT(" + ")), ComboBase, Multiplier);
}
