```mermaid
---
config:
  theme: default
  look: classic
  layout: elk
---
flowchart TB
    subgraph API["Backend.API"]
        Routes["Routes"]
        Controllers["Controllers"]
        DTOs["DTOs"]
        ApiDI["DependencyInjection"]
    end

    subgraph BLL["Backend.BLL"]
        Interfaces["Interfaces"]
        Services["Services"]
        BllDI["DependencyInjection"]
    end

    subgraph DAL["Backend.DAL"]
        Repositories["Repositories"]
        DbContext["AppDbContext"]
        DalDI["DependencyInjection"]
    end

    subgraph Models["Backend.Models"]
        DomainModels["Domain models"]
    end

    Program["Program.cs<br/>composition root"]

    Program --> ApiDI
    Program --> BllDI
    Program --> DalDI
    Program --> Routes

    Routes --> Controllers
    Controllers --> Interfaces
    Services --> Interfaces
    Services --> Repositories
    Repositories --> DbContext

    Controllers --> DomainModels
    Services --> DomainModels
    Repositories --> DomainModels
    DbContext --> DomainModels
    DTOs -.-> Controllers

    API -->|"project ref"| BLL
    API -->|"project ref<br/>(composition root)"| DAL
    API -->|"project ref"| Models
    BLL -->|"project ref"| DAL
    BLL -->|"project ref"| Models
    DAL -->|"project ref"| Models
```