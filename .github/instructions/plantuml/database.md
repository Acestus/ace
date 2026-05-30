```plantuml
@startuml DB <APP_NAME> UAT
title AWS Aurora DB Connection

!define AWSPuml https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v19.0/dist
!includeurl AWSPuml/AWSSimplified.puml
!include AWSPuml/AWSCommon.puml
!include AWSPuml/Database/AuroraMySQLInstance.puml
!include AWSPuml/NetworkingContentDelivery/ClientVPN.puml
!include AWSPuml/NetworkingContentDelivery/VPCVirtualprivatecloudVPC.puml
!include AWSPuml/General/Users.puml
!include AWSPuml/General/Servers.puml

left to right direction

agent "<APP_NAME> Link" as <app_name>data

rectangle "<APP_NAME> AWS Account" as <app_name>account {
    VPCVirtualprivatecloudVPC(<app_name>vpc, "<APP_NAME> VPC", "10.0.192.0/19") {
        AuroraMySQLInstance(<app_name>db, "<APP_NAME> Aurora DB", "Aurora MySQL 8.0")
    }
}
rectangle "<ORG_NAME> AWS Account" as <org_short>account {
    VPCVirtualprivatecloudVPC(<org_short>vpc, "<APP_NAME> VPC", "10.0.0.0/24") {
        AuroraMySQLInstance(<org_short>db, "<APP_NAME> Aurora DB", "<DB_HOST>.rds.amazonaws.com")
    }
}

ClientVPN(vpn, "On-Prem VPN", "GlobalProtect")
Users(Users, "Users", "EDM Team")
Servers(JavaServices, "Java Services", "AppDev Team")

<app_name>data --> <app_name>db
<app_name>db --> <org_short>db : VPC Peering
<org_short>db --> vpn
vpn --> Users
vpn --> JavaServices

@enduml
```

```plantuml
@startuml Basic Usage - AWS IoT Rules Engine
' Uncomment the line below for "dark mode" styling
'!$AWS_DARK = true

!define AWSPuml https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v19.0/dist
!includeurl AWSPuml/AWSSimplified.puml
!include AWSPuml/AWSCommon.puml
!include AWSPuml/InternetOfThings/IoTRule.puml
!include AWSPuml/Analytics/KinesisDataStreams.puml
!include AWSPuml/ApplicationIntegration/SimpleQueueService.puml

left to right direction

agent "Published Event" as event

IoTRule(iotRule, "Action Error Rule", "error if Kinesis fails")
KinesisDataStreams(eventStream, "IoT Events", "2 shards")
SimpleQueueService(errorQueue, "Rule Error Queue", "failed Rule actions")

event --> iotRule : JSON message
iotRule --> eventStream : messages
iotRule --> errorQueue : Failed action message

@enduml
```

```plantuml
@startuml Option 1
title Azure Option 1: Similar to Current Infrastruture

!define AzurePuml https://raw.githubusercontent.com/plantuml-stdlib/Azure-PlantUML/master/dist
!includeurl AzurePuml/AzureSimplified.puml
!includeurl AzurePuml/AzureCommon.puml
!includeurl AzurePuml/Compute/AzureVirtualMachine.puml
!includeurl AzurePuml/Databases/AzureSqlDatabase.puml
!includeurl AzurePuml/Compute/AzureServiceFabric.puml
!includeurl AzurePuml/Analytics/PowerBI.puml
!includeurl AzurePuml/Containers/AzureKubernetesService.puml
!includeurl AzurePuml/Analytics/AzureDatabricks.puml

AzureVirtualMachine(Prod01, "Prod01", "On-prem SQL Server")
cloud "Azure" {
    AzureSqlDatabase(Prod02, "Prod02", "Azure SQL Hyperscale")
    PowerBI(PowerBI, "Power BI Reports", "PowerBI reports off Prod02, Star Schema")
    AzureKubernetesService(Apps, "Applications", "Web Service API calls from Prod02, AKS")
    AzureDatabricks(Databricks, "Databricks", "Ingest to Databricks or Connect Directly with Jupyter Notebooks")
}

DataSources -right-> Prod01
Prod01 --right--> Prod02: A few seconds to upload data
Prod02 --> PowerBI: Optional
Prod02 -right-> Apps: Schema on read
Prod02 -down-> Databricks: Optional

@enduml
```

```plantuml
@startuml 
!define AWS https://raw.githubusercontent.com/plantuml-stdlib/AWS/master/dist
!includeurl AzurePuml/AzureSimplified.puml
!includeurl AzurePuml/AzureCommon.puml
!includeurl AzurePuml/Compute/AzureServiceFabric.puml
!includeurl AzurePuml/Compute/AzureVirtualMachine.puml
!includeurl AzurePuml/Databases/AzureDatabaseForMySQL.puml
!includeurl AzurePuml/Databases/AzureDataFactory.puml
!includeurl AzurePuml/Analytics/AzureSynapseAnalytics.puml
!includeurl AzurePuml/Media/AzureMediaFile.puml

node "App Service Plan" {
    AzureServiceFabric(MicrosoftFabric, "Microsoft Fabric", "test")
}
node "Azure Naming Tool" {
    AzureVirtualMachine(LiftandShiftVM, "Lift and Shift VM", "test")
    AzureDatabaseForMySQL(MySQLFlexibleInstance, "MySQL Flexible Instance", "test")
    AzureDataFactory(datafactory, "Azure Datafactory", "test")
    AzureSynapseAnalytics(synapse, "Azure Synapse Analytics", "test")
    AzureMediaFile(Snowflake, "Snowflake", "test")
}

node "IPAM" {
    AzureServiceFabric(MicrosoftFabric2, "Microsoft Fabric", "test")
    AzureVirtualMachine(LiftandShiftVM2, "Lift and Shift VM", "test")
    AzureDatabaseForMySQL(MySQLFlexibleInstance2, "MySQL Flexible Instance", "test")
    AzureDataFactory(datafactory2, "Azure Datafactory", "test")
    AzureSynapseAnalytics(synapse2, "Azure Synapse Analytics", "test")
    AzureMediaFile(Snowflake2, "Snowflake", "test")
}

```

```plantuml
@startuml

!define AzurePuml https://raw.githubusercontent.com/plantuml-stdlib/Azure-PlantUML/master/dist
!includeurl AzurePuml/AzureSimplified.puml
!includeurl AzurePuml/AzureCommon.puml
!includeurl AzurePuml/Compute/AzureServiceFabric.puml
!includeurl AzurePuml/Compute/AzureVirtualMachine.puml
!includeurl AzurePuml/Databases/AzureDatabaseForMySQL.puml
!includeurl AzurePuml/Databases/AzureDataFactory.puml
!includeurl AzurePuml/Analytics/AzureSynapseAnalytics.puml
!includeurl AzurePuml/Media/AzureMediaFile.puml


AzureServiceFabric(MicrosoftFabric, "Microsoft Fabric", "<USER_A> said his solution is instantaneous, but there is no SLA for sub-second response times")
AzureVirtualMachine(LiftandShiftVM, "Lift and Shift VM", "Beefy Server for Beefy Workloads. Do not have to rewrite the queries")
AzureDatabaseForMySQL(MySQLFlexibleInstance, "MySQL Flexible Instance", "Mautic is a MySQL Database")
AzureDataFactory(datafactory, "Azure Datafactory", "Microsoft wants to replace ADF with Fabric Datafactory")
AzureSynapseAnalytics(synapse, "Azure Synapse Analytics", "Microsoft wants to replace Synapse with Fabric Datafactory")
AzureMediaFile(Snowflake, "Snowflake", "With Snowflake’s elastic multi-cluster compute, you can easily scale up resources to quickly ingest and process new data, and you can scale out dashboards and analytics to tens of thousands of end consumers with workload isolation and no performance degradation.")
(Database Solutions) -down-> (AWS)
(Database Solutions) -down-> (Other Cloud)
(Database Solutions) -down-> (On-Prem)
(Database Solutions) -down-> (Azure)
(Other Cloud) -down-> (Snowflake)
(Azure) -down-> synapse
(Azure) -down-> datafactory
(Azure) -down-> LiftandShiftVM
(Azure) -down-> MySQLFlexibleInstance
(Azure) -down-> MicrosoftFabric


@enduml
```


```plantuml
@startuml

!define AzurePuml https://raw.githubusercontent.com/plantuml-stdlib/Azure-PlantUML/release/2-2/dist
!includeurl AzurePuml/AzureSimplified.puml
!include <azure/All>



AzureDataFactory(datafactory, "Azure Datafactory", "Replaces Java Services")
AzureServiceFabric(MicrosoftFabric, "Microsoft Fabric", "Azure Datafactory")

datafactory -right-> MicrosoftFabric

@enduml
```

```plantuml
@startuml

!define AzurePuml https://raw.githubusercontent.com/plantuml-stdlib/Azure-PlantUML/release/2-2/dist
!includeurl AzurePuml/AzureSimplified.puml
!include <azure/All>

AzureServiceFabric(MicrosoftFabric, "Microsoft Fabric", "<USER_A> said his solution is instantaneous, but there is no SLA for sub-second response times")
AzureVirtualMachine(LiftandShiftVM, "Lift and Shift VM", "Beefy Server for Beefy Workloads")
AzureDatabaseForMySQL(MySQLFlexibleInstance, "MySQL Flexible Instance", "Mautic is a MySQL Database")
(Database Solutions) -down-> (AWS)
(Database Solutions) -down-> (Other Cloud)
(Database Solutions) -down-> (On-Prem)
(Database Solutions) -down-> (Azure)
(Azure) -down-> LiftandShiftVM
(Azure) -down-> MySQLFlexibleInstance
(Azure) -down-> MicrosoftFabric


@enduml
```


