#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "JBIHUD.generated.h"

/** Debug-style HUD: score, current combo, ride mode. Replace with UMG later. */
UCLASS()
class JBI_API AJBIHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

private:
	int32 ShownBanked = 0;
	float BankedTimer = 0.f;
};
