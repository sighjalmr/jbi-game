#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "SkateMovementComponent.h"
#include "JBICharacter.generated.h"

class UCameraComponent;
class USpringArmComponent;
class UInputAction;
class UInputMappingContext;
class UTrickComponent;
class UStaticMeshComponent;
struct FInputActionValue;

/**
 * The player: walks like in Bully, rides a skateboard or BMX like in Tony Hawk.
 * Input actions are built in code so the prototype runs without any input assets.
 *
 * Keyboard: WASD move/steer, Space ollie, Shift brake, F board, B bike,
 *           J kickflip, K heelflip, L shove-it, I grab.
 * Gamepad:  left stick, A ollie, B brake, Y board, D-pad up bike, X/RB/LB/RT tricks.
 */
UCLASS()
class JBI_API AJBICharacter : public ACharacter
{
	GENERATED_BODY()

public:
	AJBICharacter(const FObjectInitializer& ObjectInitializer);

	UFUNCTION(BlueprintPure, Category = "JBI")
	USkateMovementComponent* GetSkateMovement() const { return SkateMovement; }

	UFUNCTION(BlueprintPure, Category = "JBI")
	UTrickComponent* GetTricks() const { return Tricks; }

	virtual void Tick(float DeltaSeconds) override;
	virtual void Landed(const FHitResult& Hit) override;
	virtual void OnJumped_Implementation() override;

protected:
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
	TObjectPtr<USpringArmComponent> CameraBoom;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Camera")
	TObjectPtr<UCameraComponent> Camera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "JBI")
	TObjectPtr<UTrickComponent> Tricks;

	/** Placeholder body until a real skeletal mesh is set up. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "JBI")
	TObjectPtr<UStaticMeshComponent> PlaceholderBody;

	/** Placeholder board/bike, shown while riding. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "JBI")
	TObjectPtr<UStaticMeshComponent> PlaceholderRide;

	/** Air spin speed, degrees per second at full steer. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "JBI")
	float AirSpinRate = 420.f;

private:
	UPROPERTY()
	TObjectPtr<USkateMovementComponent> SkateMovement;

	UPROPERTY()
	TObjectPtr<UInputMappingContext> Mapping;

	UPROPERTY()
	TObjectPtr<UInputAction> MoveAction;
	UPROPERTY()
	TObjectPtr<UInputAction> LookAction;
	UPROPERTY()
	TObjectPtr<UInputAction> JumpAction;
	UPROPERTY()
	TObjectPtr<UInputAction> BrakeAction;
	UPROPERTY()
	TObjectPtr<UInputAction> BoardAction;
	UPROPERTY()
	TObjectPtr<UInputAction> BikeAction;
	UPROPERTY()
	TObjectPtr<UInputAction> KickflipAction;
	UPROPERTY()
	TObjectPtr<UInputAction> HeelflipAction;
	UPROPERTY()
	TObjectPtr<UInputAction> ShoveItAction;
	UPROPERTY()
	TObjectPtr<UInputAction> GrabAction;

	void BuildInput();

	void Move(const FInputActionValue& Value);
	void MoveReleased(const FInputActionValue& Value);
	void Look(const FInputActionValue& Value);
	void BrakeStart(const FInputActionValue& Value);
	void BrakeStop(const FInputActionValue& Value);
	void ToggleBoard(const FInputActionValue& Value);
	void ToggleBike(const FInputActionValue& Value);
	void Kickflip(const FInputActionValue& Value);
	void Heelflip(const FInputActionValue& Value);
	void ShoveIt(const FInputActionValue& Value);
	void Grab(const FInputActionValue& Value);

	void AirTrick(FName BoardName, FName BikeName, int32 Points, float Duration);

	bool bWasGrinding = false;
	float AirSpin = 0.f;
	float SteerAxis = 0.f;
};
