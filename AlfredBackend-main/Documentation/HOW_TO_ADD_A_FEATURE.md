# How to add a feature (beginner guide)

This guide walks you through adding a new feature to the backend,
**file by file**, even if you are not comfortable with OOP yet.

Before you start, open the existing `Example*` files and keep them
side by side. You will mostly **copy that pattern** and rename it.

Useful commands are listed in `commands.md`.

---

## Tiny OOP vocabulary (only what you need)

| Word | Simple meaning |
| --- | --- |
| **Class** | A blueprint for an object (data + behavior). Example: `ExampleService` |
| **Object / instance** | One concrete use of a class, created by the app when needed |
| **Property** | A piece of data on a class (`Name`, `Id`, …) |
| **Method** | A function that belongs to a class |
| **Interface** (`ISomething`) | A contract: “this type must provide these methods”. Useful for testing and DI |
| **Dependency Injection (DI)** | The app builds and gives you the objects you need (service, controller, …) instead of you writing `new` everywhere |
| **Layer** | A project with one job (API, business logic, database, models) |

You do **not** need to invent a new architecture. Follow the layers below.

---

## Big picture: what happens when someone calls your API

```
Browser / frontend
        │
        ▼
1. Route          (URL + HTTP method)     Backend.API/Routes
        │
        ▼
2. Controller     (glue: DTO → service)   Backend.API/Controllers
        │
        ▼
3. Service        (business rules)        Backend.BLL/Services
        │
        ▼
4. Repository     (talk to the database)  Backend.DAL/Repositories   ← only if you save data
        │
        ▼
5. Model          (shape of the data)     Backend.Models
```

Rule of thumb:

- **Route** = “where is the door?”
- **DTO** = “what data is allowed to enter?”
- **Controller** = “who do I call next?”
- **Service** = “what is the real work?”
- **Repository** = “how do I read/write the database?”
- **Model** = “what does this data look like inside the app?”

---

## Choose a feature name

Pick **one** PascalCase name and reuse it everywhere.

Examples: `Device`, `Home`, `User`, `Scene`

In this guide we use **`Device`**.  
Replace `Device` with your own name in every file.

---

## Checklist

```
[ ] Step 1  — Model
[ ] Step 2  — Repository (+ database)   [skip if no DB yet]
[ ] Step 3  — Service interface
[ ] Step 4  — Service implementation
[ ] Step 5  — Register the service (BLL DI)
[ ] Step 6  — DTOs
[ ] Step 7  — Controller
[ ] Step 8  — Register the controller (API DI)
[ ] Step 9  — Routes
[ ] Step 10 — Map the routes in Program.cs
[ ] Step 11 — Build and test
```

Work **from the bottom of the stack upward** (model → … → route).
That way each file can already use the previous one.

---

## Step 1 — Model

**File to create:** `Backend.Models/DeviceModels.cs`

**Role:** describe the data. No logic. Only properties.

Look at: `Backend.Models/ExampleModels.cs`

Minimal shape:

```csharp
namespace Backend.Models;

public class Device {
    public Guid Id { get; set; }
    public required string Name { get; set; }
}
```

Notes for beginners:

- `{ get; set; }` means “this value can be read and written”
- `required` means “you must set this when creating the object”
- `Guid` is a unique id (search “C# Guid” if needed)

---

## Step 2 — Repository and database (only if you persist data)

Skip this whole step if your feature does not touch the database yet
(like the current `Example` feature).

### 2.1 Register the model in EF

**File to edit:** `Backend.DAL/Database.cs` (`AppDbContext`)

Add a `DbSet` so EF knows the table exists, for example:

```csharp
public DbSet<Device> Devices => Set<Device>();
```

Add relationships in `OnModelCreating` only when you need them
(see the commented example already in that file).

### 2.2 Repository interface

**File to create:** `Backend.DAL/Repositories/IDeviceRepository.cs`
(or an `Interfaces` folder if you prefer; stay consistent once you choose)

**Role:** list the database operations the rest of the app is allowed to use.

```csharp
using Backend.Models;

namespace Backend.DAL.Repositories;

public interface IDeviceRepository {
    Task<Device?> GetByIdAsync(Guid id);
    Task AddAsync(Device device);
}
```

### 2.3 Repository implementation

**File to create:** `Backend.DAL/Repositories/DeviceRepository.cs`

**Role:** real SQL/EF code. Only this layer talks to `AppDbContext`.

The class should implement `IDeviceRepository` and receive `AppDbContext`
through its constructor (DI will provide it).

### 2.4 Register the repository

**File to edit:** `Backend.DAL/DependencyInjection.cs`

Inside `AddDAL()`, add:

```csharp
services.AddScoped<IDeviceRepository, DeviceRepository>();
```

Meaning in plain words:
“When someone asks for `IDeviceRepository`, give them a `DeviceRepository`.”

### 2.5 Migration

When the model is ready, create and apply a migration
(see `commands.md`):

```bash
dotnet ef migrations add AddDevice --project Backend.DAL --startup-project Backend.API
dotnet ef database update --project Backend.DAL --startup-project Backend.API
```

---

## Step 3 — Service interface

**File to create:** `Backend.BLL/Interfaces/IDeviceService.cs`

**Role:** declare what the business layer can do, without saying how.

Look at: `Backend.BLL/Interfaces/IExampleService.cs`

```csharp
using Backend.Models;

namespace Backend.BLL.Interfaces;

public interface IDeviceService {
    Device GetDevice(string name);
}
```

Why an interface?

- The controller depends on `IDeviceService`, not on the concrete class
- Later you can mock it in tests without touching the database

---

## Step 4 — Service implementation

**File to create:** `Backend.BLL/Services/DeviceService.cs`

**Role:** business logic (rules, calculations, orchestration).

Look at: `Backend.BLL/Services/ExampleService.cs`

```csharp
using Backend.Models;
using Backend.BLL.Interfaces;

namespace Backend.BLL.Services;

public class DeviceService : IDeviceService {
    public Device GetDevice(string name) {
        return new Device {
            Id = Guid.NewGuid(),
            Name = name
        };
    }
}
```

If you have a repository, inject it in the constructor:

```csharp
public class DeviceService(
    IDeviceRepository _deviceRepository
) : IDeviceService {
    // call _deviceRepository inside your methods
}
```

Rules:

- Put business decisions here
- Do **not** read HTTP details here (no DTOs from the API project)
- Do **not** use `AppDbContext` directly here (use the repository)

---

## Step 5 — Register the service

**File to edit:** `Backend.BLL/DependencyInjection.cs`

Inside `AddBLL()`, add:

```csharp
services.AddScoped<IDeviceService, DeviceService>();
```

If you forget this line, the app may compile but crash at runtime with
“Unable to resolve service…”.

---

## Step 6 — DTOs

**File to create:** `Backend.API/DTOs/DeviceDTOs.cs`

**Role:** validate and shape data that enters (or leaves) the HTTP API.

Look at: `Backend.API/DTOs/ExampleDTOs.cs`

```csharp
using System.ComponentModel.DataAnnotations;
using Microsoft.AspNetCore.Mvc;

namespace Backend.API.DTOs;

public sealed class GetDeviceDTO {
    [FromQuery]
    [Required(ErrorMessage = "The name is needed !")]
    [MinLength(1, ErrorMessage = "The name must not be empty !")]
    public string Name { get; init; } = string.Empty;
}
```

Notes:

- A **DTO** is not your database model. It is the “form” of the request/response
- Attributes like `[Required]` describe validation rules
- For Minimal APIs, also enable `builder.Services.AddValidation();` in `Program.cs`
  if you want those attributes to reject bad requests automatically

---

## Step 7 — Controller

**File to create:** `Backend.API/Controllers/DeviceController.cs`

**Role:** thin glue between the route and the service.

Look at: `Backend.API/Controllers/ExampleController.cs`

```csharp
using Backend.API.DTOs;
using Backend.Models;
using Backend.BLL.Interfaces;

namespace Backend.API.Controllers;

public class DeviceController(
    IDeviceService _deviceService
) {
    public Device GetDevice(GetDeviceDTO dto) {
        return _deviceService.GetDevice(dto.Name);
    }
}
```

What this file should do:

- Take a validated DTO
- Call one (or a few) service methods
- Return the result

What it should **not** do:

- Contain heavy business rules
- Talk to the database / `AppDbContext`

---

## Step 8 — Register the controller

**File to edit:** `Backend.API/DependencyInjection.cs`

Inside `AddAPI()`, add:

```csharp
services.AddScoped<DeviceController>();
```

Same idea as the service: without this line, the route cannot receive
the controller from DI.

---

## Step 9 — Routes

**File to create:** `Backend.API/Routes/DeviceRoute.cs`

**Role:** expose the HTTP endpoint(s).

Look at: `Backend.API/Routes/ExampleRoute.cs`

```csharp
using Backend.API.Controllers;
using Backend.API.DTOs;

namespace Backend.API.Routes;

public static class DeviceRoutes {
    public static void MapDeviceRoutes(this IEndpointRouteBuilder mainRouter) {
        var deviceRouter = mainRouter.MapGroup("/device");

        deviceRouter.MapGet("/by_name", (
            DeviceController controller,
            [AsParameters] GetDeviceDTO dto
        ) => {
            return controller.GetDevice(dto);
        });
    }
}
```

Important binding rule:

- On a **GET**, a complex DTO must use `[AsParameters]`
  so ASP.NET reads query params (`?name=lamp`) instead of a JSON body
- GET requests do not have a body

Example URL after this step:

`GET /device/by_name?name=lamp`

---

## Step 10 — Wire the routes in Program.cs

**File to edit:** `Backend.API/Program.cs`

1. Make sure the using exists:

```csharp
using Backend.API.Routes;
```

2. After the other `Map…Routes()` calls, add:

```csharp
app.MapDeviceRoutes();
```

`AddDAL()`, `AddBLL()`, and `AddAPI()` should already be called.
You usually only add a new `Map…` line here for a new feature.

---

## Step 11 — Build and test

```bash
dotnet build
dotnet run --project Backend.API
```

Then open Swagger (development) and try your new route.

If something fails, check these common mistakes first:

| Symptom | Likely cause |
| --- | --- |
| `Unable to resolve service for type '…'` | Missing line in a `DependencyInjection.cs` |
| `Body was inferred but the method does not allow…` | Missing `[AsParameters]` on a GET DTO |
| Project / namespace errors | Wrong folder or forgotten `using` |
| Validation never rejects bad input | `AddValidation()` not registered in `Program.cs` |

---

## File map (one feature = these places)

For a feature named `Device`, you typically touch:

```
Backend.Models/
  DeviceModels.cs

Backend.DAL/                          (only if persistence)
  Database.cs                         (edit AppDbContext)
  Repositories/IDeviceRepository.cs
  Repositories/DeviceRepository.cs
  DependencyInjection.cs              (edit)

Backend.BLL/
  Interfaces/IDeviceService.cs
  Services/DeviceService.cs
  DependencyInjection.cs              (edit)

Backend.API/
  DTOs/DeviceDTOs.cs
  Controllers/DeviceController.cs
  Routes/DeviceRoute.cs
  DependencyInjection.cs              (edit)
  Program.cs                          (edit: MapDeviceRoutes)
```

---

## Golden rules (short)

1. Copy `Example*`, then rename carefully
2. One feature name, reused in every layer
3. Never skip layers (Controller must not call the repository directly)
4. Always register new services/controllers/repositories in DI
5. Keep each file focused on its job
6. Write code and comments in **English**

If you are stuck, open the matching `Example*` file for that layer and
mirror it line by line with your feature name.
)
