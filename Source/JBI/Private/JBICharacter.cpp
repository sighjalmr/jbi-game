#include "JBICharacter.h"

#include "GrindRail.h"
#include "TrickComponent.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/LocalPlayer.h"
#include "Engine/StaticMesh.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputModifiers.h"
#include "UObject/ConstructorHelpers.h"

AJBICharacter::AJBICharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.SetDefaultSubobjectClass<USkateMovementComponent>(ACharacter::CharacterMovementComponentName))
{
	PrimaryActorTick.bCanEverTick = true;

	SkateMovement = Cast<USkateMovementComponent>(GetCharacterMovement());
	SkateMovement->bOrientRotationToMovement = true;
	SkateMovement->RotationRate = FRotator(0.f, 540.f, 0.f);
	SkateMovement->MaxWalkSpeed = 500.f;
	SkateMovement->JumpZVelocity = 420.f;
	SkateMovement->AirControl = 0.2f;

	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;

	GetCapsuleComponent()->InitCapsuleSize(35.f, 90.f);

	CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
	CameraBoom->SetupAttachment(RootComponent);
	CameraBoom->TargetArmLength = 450.f;
	CameraBoom->SocketOffset = FVector(0.f, 0.f, 80.f);
	CameraBoom->bUsePawnControlRotation = true;
	CameraBoom->bEnableCameraLag = true;
	CameraBoom->CameraLagSpeed = 8.f;

	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
	Camera->bUsePawnControlRotation = false;

	Tricks = CreateDefaultSubobject<UTrickComponent>(TEXT("Tricks"));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));

	PlaceholderBody = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PlaceholderBody"));
	PlaceholderBody->SetupAttachment(RootComponent);
	PlaceholderBody->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	PlaceholderBody->SetRelativeScale3D(FVector(0.6f, 0.6f, 1.7f));
	PlaceholderBody->SetRelativeLocation(FVector(0.f, 0.f, -5.f));
	if (Cylinder.Succeeded())
	{
		PlaceholderBody->SetStaticMesh(Cylinder.Object);
	}

	PlaceholderRide = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PlaceholderRide"));
	PlaceholderRide->SetupAttachment(RootComponent);
	PlaceholderRide->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	PlaceholderRide->SetRelativeScale3D(FVector(0.8f, 0.22f, 0.04f));
	PlaceholderRide->SetRelativeLocation(FVector(0.f, 0.f, -86.f));
	PlaceholderRide->SetVisibility(false);
	if (Cube.Succeeded())
	{
		PlaceholderRide->SetStaticMesh(Cube.Object);
	}
}

void AJBICharacter::BuildInput()
{
	auto MakeAction = [this](const TCHAR* Name, EInputActionValueType Type)
	{
		UInputAction* Action = NewObject<UInputAction>(this, Name);
		Action->ValueType = Type;
		return Action;
	};
	MoveAction = MakeAction(TEXT("IA_Move"), EInputActionValueType::Axis2D);
	LookAction = MakeAction(TEXT("IA_Look"), EInputActionValueType::Axis2D);
	JumpAction = MakeAction(TEXT("IA_Jump"), EInputActionValueType::Boolean);
	BrakeAction = MakeAction(TEXT("IA_Brake"), EInputActionValueType::Boolean);
	BoardAction = MakeAction(TEXT("IA_Board"), EInputActionValueType::Boolean);
	BikeAction = MakeAction(TEXT("IA_Bike"), EInputActionValueType::Boolean);
	KickflipAction = MakeAction(TEXT("IA_Kickflip"), EInputActionValueType::Boolean);
	HeelflipAction = MakeAction(TEXT("IA_Heelflip"), EInputActionValueType::Boolean);
	ShoveItAction = MakeAction(TEXT("IA_ShoveIt"), EInputActionValueType::Boolean);
	GrabAction = MakeAction(TEXT("IA_Grab"), EInputActionValueType::Boolean);

	Mapping = NewObject<UInputMappingContext>(this, TEXT("IMC_JBI"));

	// WASD -> 2D axis: W/S drive Y (swizzled), A/S are negated.
	Mapping->MapKey(MoveAction, EKeys::W).Modifiers.Add(NewObject<UInputModifierSwizzleAxis>(Mapping));
	{
		FEnhancedActionKeyMapping& S = Mapping->MapKey(MoveAction, EKeys::S);
		S.Modifiers.Add(NewObject<UInputModifierSwizzleAxis>(Mapping));
		S.Modifiers.Add(NewObject<UInputModifierNegate>(Mapping));
	}
	Mapping->MapKey(MoveAction, EKeys::A).Modifiers.Add(NewObject<UInputModifierNegate>(Mapping));
	Mapping->MapKey(MoveAction, EKeys::D);
	Mapping->MapKey(MoveAction, EKeys::Gamepad_Left2D).Modifiers.Add(NewObject<UInputModifierDeadZone>(Mapping));

	auto NegateY = [this]()
	{
		UInputModifierNegate* Negate = NewObject<UInputModifierNegate>(Mapping);
		Negate->bX = false;
		Negate->bY = true;
		Negate->bZ = false;
		return Negate;
	};
	Mapping->MapKey(LookAction, EKeys::Mouse2D).Modifiers.Add(NegateY());
	{
		FEnhancedActionKeyMapping& Stick = Mapping->MapKey(LookAction, EKeys::Gamepad_Right2D);
		Stick.Modifiers.Add(NewObject<UInputModifierDeadZone>(Mapping));
		Stick.Modifiers.Add(NegateY());
	}

	Mapping->MapKey(JumpAction, EKeys::SpaceBar);
	Mapping->MapKey(JumpAction, EKeys::Gamepad_FaceButton_Bottom);
	Mapping->MapKey(BrakeAction, EKeys::LeftShift);
	Mapping->MapKey(BrakeAction, EKeys::Gamepad_FaceButton_Right);
	Mapping->MapKey(BoardAction, EKeys::F);
	Mapping->MapKey(BoardAction, EKeys::Gamepad_FaceButton_Top);
	Mapping->MapKey(BikeAction, EKeys::B);
	Mapping->MapKey(BikeAction, EKeys::Gamepad_DPad_Up);
	Mapping->MapKey(KickflipAction, EKeys::J);
	Mapping->MapKey(KickflipAction, EKeys::Gamepad_FaceButton_Left);
	Mapping->MapKey(HeelflipAction, EKeys::K);
	Mapping->MapKey(HeelflipAction, EKeys::Gamepad_RightShoulder);
	Mapping->MapKey(ShoveItAction, EKeys::L);
	Mapping->MapKey(ShoveItAction, EKeys::Gamepad_LeftShoulder);
	Mapping->MapKey(GrabAction, EKeys::I);
	Mapping->MapKey(GrabAction, EKeys::Gamepad_RightTrigger);
}

void AJBICharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	if (!Mapping)
	{
		BuildInput();
	}
	if (const APlayerController* PC = Cast<APlayerController>(GetController()))
	{
		if (UEnhancedInputLocalPlayerSubsystem* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
		{
			Subsystem->AddMappingContext(Mapping, 0);
		}
	}

	UEnhancedInputComponent* Input = Cast<UEnhancedInputComponent>(PlayerInputComponent);
	if (!Input)
	{
		UE_LOG(LogTemp, Error, TEXT("JBI: Enhanced Input is not the default input component, check Config/DefaultInput.ini"));
		return;
	}
	Input->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AJBICharacter::Move);
	Input->BindAction(MoveAction, ETriggerEvent::Completed, this, &AJBICharacter::MoveReleased);
	Input->BindAction(LookAction, ETriggerEvent::Triggered, this, &AJBICharacter::Look);
	Input->BindAction(JumpAction, ETriggerEvent::Started, this, &ACharacter::Jump);
	Input->BindAction(JumpAction, ETriggerEvent::Completed, this, &ACharacter::StopJumping);
	Input->BindAction(BrakeAction, ETriggerEvent::Started, this, &AJBICharacter::BrakeStart);
	Input->BindAction(BrakeAction, ETriggerEvent::Completed, this, &AJBICharacter::BrakeStop);
	Input->BindAction(BoardAction, ETriggerEvent::Started, this, &AJBICharacter::ToggleBoard);
	Input->BindAction(BikeAction, ETriggerEvent::Started, this, &AJBICharacter::ToggleBike);
	Input->BindAction(KickflipAction, ETriggerEvent::Started, this, &AJBICharacter::Kickflip);
	Input->BindAction(HeelflipAction, ETriggerEvent::Started, this, &AJBICharacter::Heelflip);
	Input->BindAction(ShoveItAction, ETriggerEvent::Started, this, &AJBICharacter::ShoveIt);
	Input->BindAction(GrabAction, ETriggerEvent::Started, this, &AJBICharacter::Grab);
}

void AJBICharacter::Move(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	if (!SkateMovement->IsRiding())
	{
		// On foot: camera-relative, like any third-person game.
		const FRotator Yaw(0.f, GetControlRotation().Yaw, 0.f);
		AddMovementInput(FRotationMatrix(Yaw).GetUnitAxis(EAxis::X), Axis.Y);
		AddMovementInput(FRotationMatrix(Yaw).GetUnitAxis(EAxis::Y), Axis.X);
		return;
	}
	// Riding: forward pushes, sideways steers (or spins in the air), back brakes.
	SteerAxis = Axis.X;
	if (Axis.Y > 0.f && SkateMovement->IsMovingOnGround())
	{
		AddMovementInput(GetActorForwardVector(), Axis.Y);
	}
	SkateMovement->SetBraking(Axis.Y < -0.5f);
}

void AJBICharacter::MoveReleased(const FInputActionValue& Value)
{
	SteerAxis = 0.f;
	SkateMovement->SetBraking(false);
}

void AJBICharacter::Look(const FInputActionValue& Value)
{
	const FVector2D Axis = Value.Get<FVector2D>();
	AddControllerYawInput(Axis.X);
	AddControllerPitchInput(Axis.Y);
}

void AJBICharacter::BrakeStart(const FInputActionValue& Value)
{
	SkateMovement->SetBraking(true);
}

void AJBICharacter::BrakeStop(const FInputActionValue& Value)
{
	SkateMovement->SetBraking(false);
}

void AJBICharacter::ToggleBoard(const FInputActionValue& Value)
{
	const bool bOn = SkateMovement->GetRideMode() != ERideMode::Skateboard;
	SkateMovement->SetRideMode(bOn ? ERideMode::Skateboard : ERideMode::OnFoot);
	PlaceholderRide->SetVisibility(bOn);
	PlaceholderRide->SetRelativeScale3D(FVector(0.8f, 0.22f, 0.04f));
}

void AJBICharacter::ToggleBike(const FInputActionValue& Value)
{
	const bool bOn = SkateMovement->GetRideMode() != ERideMode::BMX;
	SkateMovement->SetRideMode(bOn ? ERideMode::BMX : ERideMode::OnFoot);
	PlaceholderRide->SetVisibility(bOn);
	PlaceholderRide->SetRelativeScale3D(FVector(1.6f, 0.1f, 0.6f));
}

void AJBICharacter::AirTrick(FName BoardName, FName BikeName, int32 Points, float Duration)
{
	if (SkateMovement->IsRiding() && SkateMovement->IsFalling())
	{
		Tricks->StartAirTrick(SkateMovement->GetRideMode() == ERideMode::BMX ? BikeName : BoardName, Points, Duration);
	}
}

void AJBICharacter::Kickflip(const FInputActionValue& Value) { AirTrick(TEXT("Kickflip"), TEXT("Barspin"), 100, 0.35f); }
void AJBICharacter::Heelflip(const FInputActionValue& Value) { AirTrick(TEXT("Heelflip"), TEXT("Tailwhip"), 100, 0.35f); }
void AJBICharacter::ShoveIt(const FInputActionValue& Value) { AirTrick(TEXT("Pop Shove-it"), TEXT("X-Up"), 80, 0.3f); }
void AJBICharacter::Grab(const FInputActionValue& Value) { AirTrick(TEXT("Indy Grab"), TEXT("Superman"), 150, 0.5f); }

void AJBICharacter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!SkateMovement->IsRiding())
	{
		return;
	}
	SkateMovement->SetSteerInput(SkateMovement->IsMovingOnGround() ? SteerAxis : 0.f);

	if (SkateMovement->IsFalling())
	{
		const float Spin = SteerAxis * AirSpinRate * DeltaSeconds;
		AddActorWorldRotation(FRotator(0.f, Spin, 0.f));
		AirSpin += FMath::Abs(Spin);

		if (SkateMovement->TryStartGrind())
		{
			const FName Name = SkateMovement->CurrentRail ? SkateMovement->CurrentRail->GrindName : FName(TEXT("Grind"));
			Tricks->AddTrick(SkateMovement->GetRideMode() == ERideMode::BMX ? FName(TEXT("Double Peg")) : Name, 100);
		}
	}

	const bool bGrinding = SkateMovement->IsGrinding();
	if (bGrinding)
	{
		Tricks->AddBalanceTime(DeltaSeconds);
		AirSpin = 0.f;
	}
	bWasGrinding = bGrinding;
}

void AJBICharacter::OnJumped_Implementation()
{
	Super::OnJumped_Implementation();
	if (SkateMovement->IsRiding())
	{
		Tricks->AddTrick(SkateMovement->GetRideMode() == ERideMode::BMX ? FName(TEXT("Bunnyhop")) : FName(TEXT("Ollie")), 50);
		AirSpin = 0.f;
	}
}

void AJBICharacter::Landed(const FHitResult& Hit)
{
	Super::Landed(Hit);
	if (!SkateMovement->IsRiding())
	{
		return;
	}
	if (AirSpin >= 150.f)
	{
		const int32 Degrees = FMath::RoundToInt(AirSpin / 180.f) * 180;
		Tricks->AddTrick(FName(*FString::Printf(TEXT("%d"), Degrees)), Degrees / 2);
	}
	AirSpin = 0.f;

	if (Tricks->IsFlipping())
	{
		// Still mid-flip on touchdown: eat it.
		SkateMovement->Velocity *= 0.2f;
	}
	Tricks->Land();
}
