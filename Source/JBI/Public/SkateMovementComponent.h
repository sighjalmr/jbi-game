#pragma once

#include "CoreMinimal.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "SkateMovementComponent.generated.h"

class AGrindRail;

UENUM(BlueprintType)
enum class ERideMode : uint8
{
	OnFoot,
	Skateboard,
	BMX
};

/** Values for CustomMovementMode when MovementMode == MOVE_Custom. */
enum ECustomSkateMove : uint8
{
	CMOVE_Grind = 1
};

/**
 * Character movement with a riding mode on top of walking:
 * keeps momentum, carves instead of strafing, speeds up downhill, and grinds along AGrindRail splines.
 */
UCLASS()
class JBI_API USkateMovementComponent : public UCharacterMovementComponent
{
	GENERATED_BODY()

public:
	USkateMovementComponent();

	UFUNCTION(BlueprintCallable, Category = "Skate")
	void SetRideMode(ERideMode NewMode);

	UFUNCTION(BlueprintPure, Category = "Skate")
	ERideMode GetRideMode() const { return RideMode; }

	UFUNCTION(BlueprintPure, Category = "Skate")
	bool IsRiding() const { return RideMode != ERideMode::OnFoot; }

	UFUNCTION(BlueprintPure, Category = "Skate")
	bool IsGrinding() const { return MovementMode == MOVE_Custom && CustomMovementMode == CMOVE_Grind; }

	/** -1..1 from the stick/keys, turns the rider while on the ground. */
	void SetSteerInput(float Value) { SteerInput = FMath::Clamp(Value, -1.f, 1.f); }

	void SetBraking(bool bBrake) { bBrakeHeld = bBrake; }

	/** Look for a rail under the falling rider and lock onto it. */
	bool TryStartGrind();

	UFUNCTION(BlueprintCallable, Category = "Skate")
	void StopGrind();

	// --- tuning -------------------------------------------------------------
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|Board")
	float BoardMaxSpeed = 1300.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|Board")
	float BoardPushAcceleration = 900.f;

	/** Rolling resistance when not pushing. Low = long glides. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|Board")
	float BoardRollingDeceleration = 120.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|Board")
	float BoardBrakeDeceleration = 1400.f;

	/** Degrees per second at full steer. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|Board")
	float BoardTurnRate = 150.f;

	/** Scales gravity along slopes: 1 = physically correct, lower = less runaway hills. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|Board")
	float SlopeGravityScale = 0.6f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|Board")
	float OllieZVelocity = 560.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|BMX")
	float BmxMaxSpeed = 1600.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|BMX")
	float BmxPushAcceleration = 1100.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|BMX")
	float BmxJumpZVelocity = 620.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|Grind")
	float GrindSnapRadius = 70.f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|Grind")
	float GrindMinSpeed = 450.f;

	/** Speed lost per second on a rail. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Skate|Grind")
	float GrindFriction = 60.f;

	UPROPERTY(BlueprintReadOnly, Category = "Skate|Grind")
	TObjectPtr<AGrindRail> CurrentRail;

	virtual bool CanAttemptJump() const override;
	virtual float GetMaxSpeed() const override;
	virtual float GetMaxBrakingDeceleration() const override;

protected:
	virtual void PhysWalking(float DeltaTime, int32 Iterations) override;
	virtual void PhysCustom(float DeltaTime, int32 Iterations) override;
	virtual void OnMovementModeChanged(EMovementMode PreviousMovementMode, uint8 PreviousCustomMode) override;

private:
	void PhysGrind(float DeltaTime);

	ERideMode RideMode = ERideMode::OnFoot;
	float SteerInput = 0.f;
	bool bBrakeHeld = false;

	float GrindDistance = 0.f;
	float GrindDirection = 1.f;
	float GrindSpeed = 0.f;
	double LastGrindEndTime = -1.0;

	// On-foot values, restored when getting off the board.
	float WalkSpeed = 500.f;
	float WalkGroundFriction = 8.f;
	float WalkBraking = 2000.f;
	float WalkJumpZ = 420.f;
};
