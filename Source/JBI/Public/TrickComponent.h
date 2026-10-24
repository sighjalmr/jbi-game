#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TrickComponent.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnComboBanked, int32, Points, int32, TotalScore);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnBail);

/**
 * Tony Hawk style scoring: every trick adds base points and +1 to the multiplier.
 * Landing clean banks base x multiplier into the score, bailing throws the combo away.
 */
UCLASS(ClassGroup = (JBI), meta = (BlueprintSpawnableComponent))
class JBI_API UTrickComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UTrickComponent();

	/** Start an air trick. Fails if another flip is still spinning. */
	UFUNCTION(BlueprintCallable, Category = "Tricks")
	bool StartAirTrick(FName Name, int32 Points, float Duration);

	/** Add a trick that has no animation window (ollie, grind start, manual start). */
	UFUNCTION(BlueprintCallable, Category = "Tricks")
	void AddTrick(FName Name, int32 Points);

	/** Called every frame while grinding or manualling: points trickle in with time. */
	UFUNCTION(BlueprintCallable, Category = "Tricks")
	void AddBalanceTime(float DeltaSeconds);

	/** Landed on the ground. Banks the combo, or bails if a flip was still spinning. */
	UFUNCTION(BlueprintCallable, Category = "Tricks")
	void Land();

	UFUNCTION(BlueprintCallable, Category = "Tricks")
	void Bail();

	UFUNCTION(BlueprintPure, Category = "Tricks")
	bool IsInCombo() const { return Multiplier > 0; }

	UFUNCTION(BlueprintPure, Category = "Tricks")
	bool IsFlipping() const { return FlipTimeLeft > 0.f; }

	UFUNCTION(BlueprintPure, Category = "Tricks")
	FString GetComboText() const;

	UPROPERTY(BlueprintReadOnly, Category = "Tricks")
	int32 TotalScore = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Tricks")
	int32 ComboBase = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Tricks")
	int32 Multiplier = 0;

	/** Last banked combo, for the HUD pop-up. */
	UPROPERTY(BlueprintReadOnly, Category = "Tricks")
	int32 LastBanked = 0;

	UPROPERTY(BlueprintAssignable, Category = "Tricks")
	FOnComboBanked OnComboBanked;

	UPROPERTY(BlueprintAssignable, Category = "Tricks")
	FOnBail OnBail;

	/** Points per second while balancing (grind/manual). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Tricks")
	float BalancePointsPerSecond = 150.f;

	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	TArray<FName> ComboNames;
	float FlipTimeLeft = 0.f;
	float BalanceRemainder = 0.f;

	void ResetCombo();
};
