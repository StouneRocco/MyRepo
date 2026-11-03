# Backend commands only

## GIT

```
git pull
```
Fetch the latest changes from the remote repository.

```
git add .
git commit -m "message"
```
Stage then save your changes locally.

```
git push
```
Push your local commits to the remote repository.


## DOTNET

```
dotnet restore
```
Download the project's NuGet dependencies (C# package manager).

```
dotnet build
```
Compile the solution to check for errors.

```
dotnet run --project Backend.API
```
Run the API locally.

```
cd Backend.API
dotnet watch
```
Move into `Backend.API` then run the app in hot reload mode
(reloads on every change without retyping a command).


## MIGRATIONS (Entity Framework)

```
dotnet tool install --global dotnet-ef
```
Install the EF Core tool (once per machine).

```
dotnet ef migrations add MigrationName --project Backend.DAL --startup-project Backend.API
```
Create a new migration from the updated models.

```
dotnet ef database update --project Backend.DAL --startup-project Backend.API
```
Apply pending migrations to the database.

```
dotnet ef migrations remove --project Backend.DAL --startup-project Backend.API
```
Remove the last migration (if not already applied in production).
