#include "SkateMovementComponent.h"

#include "GrindRail.h"
#include "Components/CapsuleComponent.h"
#include "Components/SplineComponent.h"
#include "EngineUtils.h"
#include "GameFramework/Character.h"

USkateMovementComponent::USkateMovementComponent()
{
}

void USkateMovementComponent::SetRideMode(ERideMode NewMode)
{
	if (NewMode == RideMode)
	{
		return;
	}
	if (RideMode == ERideMode::OnFoot)
	{
		WalkSpeed = MaxWalkSpeed;
		WalkGroundFriction = GroundFriction;
		WalkBraking = BrakingDecelerationWalking;
		WalkJumpZ = JumpZVelocity;
	}
	RideMode = NewMode;

	const bool bRiding = IsRiding();
	bOrientRotationToMovement = !bRiding;
	bUseSeparateBrakingFriction = bRiding;
	BrakingFriction = bRiding ? 0.f : BrakingFriction;

	switch (RideMode)
	{
	case ERideMode::OnFoot:
		StopGrind();
		MaxWalkSpeed = WalkSpeed;
		GroundFriction = WalkGroundFriction;
		BrakingDecelerationWalking = WalkBraking;
		JumpZVelocity = WalkJumpZ;
		MaxAcceleration = 2048.f;
		break;
	case ERideMode::Skateboard:
		GroundFriction = 0.5f;
		JumpZVelocity = OllieZVelocity;
		MaxAcceleration = BoardPushAcceleration;
		break;
	case ERideMode::BMX:
		GroundFriction = 0.8f;
		JumpZVelocity = BmxJumpZVelocity;
		MaxAcceleration = BmxPushAcceleration;
		break;
	}
}

float USkateMovementComponent::GetMaxSpeed() const
{
	if (IsRiding() && IsMovingOnGround())
	{
		return RideMode == ERideMode::BMX ? BmxMaxSpeed : BoardMaxSpeed;
	}
	return Super::GetMaxSpeed();
}

float USkateMovementComponent::GetMaxBrakingDeceleration() const
{
	if (IsRiding() && IsMovingOnGround())
	{
		return bBrakeHeld ? BoardBrakeDeceleration : BoardRollingDeceleration;
	}
	return Super::GetMaxBrakingDeceleration();
}

bool USkateMovementComponent::CanAttemptJump() const
{
	return Super::CanAttemptJump() || (IsJumpAllowed() && IsGrinding());
}

void USkateMovementComponent::PhysWalking(float DeltaTime, int32 Iterations)
{
	if (IsRiding() && UpdatedComponent && DeltaTime > 0.f)
	{
		// Carve: rotate the rider, then point the velocity where the board points (wheels don't slide sideways).
		const float Speed2D = Velocity.Size2D();
		const float TurnScale = FMath::GetMappedRangeValueClamped(FVector2D(0.f, 300.f), FVector2D(0.4f, 1.f), Speed2D);
		const FRotator Turn(0.f, SteerInput * BoardTurnRate * TurnScale * DeltaTime, 0.f);
		const FQuat NewRot = Turn.Quaternion() * UpdatedComponent->GetComponentQuat();
		MoveUpdatedComponent(FVector::ZeroVector, NewRot, false);

		const FVector Forward = UpdatedComponent->GetForwardVector().GetSafeNormal2D();
		const float Along = FVector::DotProduct(Velocity, Forward);
		const float Sign = Along >= 0.f ? 1.f : -1.f;
		Velocity = Forward * Speed2D * Sign + FVector(0.f, 0.f, Velocity.Z);

		// Hills: the part of gravity that runs along the board speeds you up or slows you down.
		if (CurrentFloor.IsWalkableFloor())
		{
			const FVector Normal = CurrentFloor.HitResult.ImpactNormal;
			const FVector Downhill = FVector::VectorPlaneProject(FVector(0.f, 0.f, GetGravityZ()), Normal);
			Velocity += Forward * FVector::DotProduct(Downhill, Forward) * SlopeGravityScale * DeltaTime;
		}
	}
	Super::PhysWalking(DeltaTime, Iterations);
}

bool USkateMovementComponent::TryStartGrind()
{
	if (!IsRiding() || !IsFalling() || Velocity.Z > 0.f || !CharacterOwner)
	{
		return false;
	}
	const double Now = GetWorld()->GetTimeSeconds();
	if (Now - LastGrindEndTime < 0.35)
	{
		return false;
	}

	const float HalfHeight = CharacterOwner->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	const FVector Feet = UpdatedComponent->GetComponentLocation() - FVector(0.f, 0.f, HalfHeight);

	AGrindRail* Best = nullptr;
	float BestDistSq = FMath::Square(GrindSnapRadius);
	float BestAlong = 0.f;
	for (AGrindRail* Rail : TActorRange<AGrindRail>(GetWorld()))
	{
		if (Rail->Spline->Bounds.ComputeSquaredDistanceFromBoxToPoint(Feet) > BestDistSq)
		{
			continue;
		}
		FVector Point;
		float Along;
		if (!Rail->FindClosest(Feet, Point, Along) || Feet.Z < Point.Z - 30.f)
		{
			continue;
		}
		const float DistSq = FVector::DistSquared(Feet, Point);
		if (DistSq < BestDistSq)
		{
			Best = Rail;
			BestDistSq = DistSq;
			BestAlong = Along;
		}
	}
	if (!Best)
	{
		return false;
	}

	const FVector Tangent = Best->Spline->GetDirectionAtDistanceAlongSpline(BestAlong, ESplineCoordinateSpace::World);
	const float Along = FVector::DotProduct(Velocity, Tangent);
	CurrentRail = Best;
	GrindDistance = BestAlong;
	GrindDirection = Along >= 0.f ? 1.f : -1.f;
	GrindSpeed = FMath::Max(FMath::Abs(Along), GrindMinSpeed);
	SetMovementMode(MOVE_Custom, CMOVE_Grind);
	return true;
}

void USkateMovementComponent::StopGrind()
{
	if (IsGrinding())
	{
		SetMovementMode(MOVE_Falling);
	}
}

void USkateMovementComponent::PhysCustom(float DeltaTime, int32 Iterations)
{
	if (CustomMovementMode == CMOVE_Grind)
	{
		PhysGrind(DeltaTime);
	}
	Super::PhysCustom(DeltaTime, Iterations);
}

void USkateMovementComponent::PhysGrind(float DeltaTime)
{
	if (!CurrentRail || !CharacterOwner || DeltaTime <= 0.f)
	{
		StopGrind();
		return;
	}
	USplineComponent* Spline = CurrentRail->Spline;
	GrindSpeed = FMath::Max(GrindSpeed - GrindFriction * DeltaTime, 200.f);
	GrindDistance += GrindDirection * GrindSpeed * DeltaTime;

	const float Clamped = FMath::Clamp(GrindDistance, 0.f, Spline->GetSplineLength());
	const FVector Dir = Spline->GetDirectionAtDistanceAlongSpline(Clamped, ESplineCoordinateSpace::World) * GrindDirection;
	Velocity = Dir * GrindSpeed;

	if (GrindDistance != Clamped)
	{
		// Ran off the end of the rail: fly on with the rail's direction.
		SetMovementMode(MOVE_Falling);
		return;
	}

	const float HalfHeight = CharacterOwner->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
	const FVector Target = Spline->GetLocationAtDistanceAlongSpline(Clamped, ESplineCoordinateSpace::World) + FVector(0.f, 0.f, HalfHeight + 2.f);
	const FQuat Facing = FRotator(0.f, Dir.Rotation().Yaw, 0.f).Quaternion();

	FHitResult Hit;
	SafeMoveUpdatedComponent(Target - UpdatedComponent->GetComponentLocation(), Facing, true, Hit);
	if (Hit.bBlockingHit)
	{
		SetMovementMode(MOVE_Falling);
	}
}

void USkateMovementComponent::OnMovementModeChanged(EMovementMode PreviousMovementMode, uint8 PreviousCustomMode)
{
	Super::OnMovementModeChanged(PreviousMovementMode, PreviousCustomMode);
	if (PreviousMovementMode == MOVE_Custom && PreviousCustomMode == CMOVE_Grind && !IsGrinding())
	{
		CurrentRail = nullptr;
		LastGrindEndTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	}
}
