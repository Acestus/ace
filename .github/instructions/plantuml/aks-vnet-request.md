![alt text](image.png)
```plantuml
@startuml

title AKS Network Requirement

!define AzurePuml https://raw.githubusercontent.com/plantuml-stdlib/Azure-PlantUML/master/dist
!includeurl AzurePuml/AzureSimplified.puml
!includeurl AzurePuml/AzureCommon.puml
!include AzurePuml/Networking/AzureVirtualNetwork.puml
!include AzurePuml/Networking/AzureSubnet.puml
!include AzurePuml/Networking/AzureVirtualNetworkPeering.puml
!include AzurePuml/Networking/AzureDNS.puml

AzureVirtualNetwork(Vnet, "AKS VNet", "/21") {
    AzureSubnet(aksSubnet01, "Manage Node Pool", "/22")
    AzureSubnet(aksSubnet02, "Azure Node Pool", "/24")
    AzureSubnet(aksSubnet03, "SQL", "/27")
    AzureSubnet(AppGateway, "API Gateway", "/28")
    AzureSubnet(PSQL, "Jenkins", "/28")
}


AzureVirtualNetworkPeering(peering, "Peering", "<REGION>-FW-HUB-VNET-10.0.0.0")
AzureDNS(dnsLinks, "DNS Links", "az.<org_short>.me")

peering -left- Vnet
Vnet -- dnsLinks

@enduml
``` 