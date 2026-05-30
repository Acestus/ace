# PowerApp

```plantuml
@startuml 
title Power Platform Update

!define AzurePuml https://raw.githubusercontent.com/plantuml-stdlib/Azure-PlantUML/master/dist
!includeurl AzurePuml/AzureSimplified.puml
!includeurl AzurePuml/AzureCommon.puml
!includeurl AzurePuml/Identity/AzureActiveDirectory.puml
!includeurl AzurePuml/Databases/AzureSqlDatabase.puml
!includeurl AzurePuml/Compute/AzureServiceFabric.puml
!includeurl AzurePuml/Integration/AzureLogicApps.puml
!define PowerPlatform https://github.com/bsorrentino/PlantUML-PowerPlatform/tree/main/dist
!includeurl PowerPlatform/powerapps.png.puml
!includeurl PowerPlatform/dataverse.png.puml
!includeurl PowerPlatform/powerautomate.png.puml


' Components
AzureActiveDirectory(EntraID, "Entra ID", "Service Principal Identity")
AzureSqlDatabase(SQLDatabase, "SQL Database", "Data Source")
dataverse(Dataverse, "Dataverse / Fabric", "Excel Alternative")
AzureLogicApps(LogicApp, "Logic App", "Email Service")
PowerApps(PowerApp, "Power App", "Analytics App")
powerautomate(PowerPlatformAdmin, "Power Platform Admin", "App Management")

' Connections
EntraID --> SQLDatabase: Service Principal Access
EntraID --> Dataverse: Recommended Excel Alternative
EntraID --> LogicApp: Email as RASupport
PowerApp --> SQLDatabase: Data Source Connection
PowerApp --> Dataverse: Future Data Connection
PowerApp --> LogicApp: Email Trigger
PowerPlatformAdmin --> PowerApp: User-Independent Management


@enduml
```
