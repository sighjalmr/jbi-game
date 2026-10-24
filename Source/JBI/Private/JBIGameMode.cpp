#include "JBIGameMode.h"

#include "JBICharacter.h"
#include "JBIHUD.h"

AJBIGameMode::AJBIGameMode()
{
	DefaultPawnClass = AJBICharacter::StaticClass();
	HUDClass = AJBIHUD::StaticClass();
}
