#include "JBIHUD.h"

#include "JBICharacter.h"
#include "TrickComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"

void AJBIHUD::DrawHUD()
{
	Super::DrawHUD();

	const AJBICharacter* Player = Cast<AJBICharacter>(GetOwningPawn());
	if (!Player || !Canvas)
	{
		return;
	}
	const UTrickComponent* Tricks = Player->GetTricks();
	const USkateMovementComponent* Move = Player->GetSkateMovement();
	UFont* Font = GEngine->GetLargeFont();

	static const TCHAR* ModeNames[] = { TEXT("On foot   [F] skateboard   [B] BMX"), TEXT("Skateboard"), TEXT("BMX") };
	DrawText(ModeNames[static_cast<int32>(Move->GetRideMode())], FLinearColor::White, 40.f, 40.f, Font, 1.2f);
	DrawText(FString::Printf(TEXT("Score: %d"), Tricks->TotalScore), FLinearColor::Yellow, 40.f, 80.f, Font, 1.6f);
	DrawText(FString::Printf(TEXT("%.0f km/h"), Move->Velocity.Size() * 0.036f), FLinearColor::White, 40.f, 130.f, Font, 1.2f);

	if (Tricks->IsInCombo())
	{
		DrawText(Tricks->GetComboText(), FLinearColor(1.f, 0.6f, 0.1f), Canvas->ClipX * 0.5f - 300.f, Canvas->ClipY - 160.f, Font, 1.5f);
	}

	// Pop-up for the last banked combo, shown for two seconds.
	if (Tricks->LastBanked != ShownBanked)
	{
		ShownBanked = Tricks->LastBanked;
		BankedTimer = 2.f;
	}
	BankedTimer -= GetWorld()->GetDeltaSeconds();
	if (BankedTimer > 0.f && ShownBanked > 0)
	{
		DrawText(FString::Printf(TEXT("+%d"), ShownBanked), FLinearColor::Green, Canvas->ClipX * 0.5f - 60.f, Canvas->ClipY * 0.35f, Font, 2.5f);
	}
}
