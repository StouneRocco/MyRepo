/**
 * Main script of the project backend.
 *
 * It uses the SwaggerUI as documentation to display the routes.
 * 
 * It implements the Dependency Injection pattern. Using
 * the services.Add<ProjectName>() method. Thanks to the
 * Microsoft.Extension dependency.
 */

//
//  Imports
//

using Backend.API;
using Backend.BLL;
using Backend.DAL;
using Backend.API.Routes;

//
//  Builder 
//

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddDAL();
builder.Services.AddBLL();
builder.Services.AddAPI();

//
//  Application
//

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}
app.UseHttpsRedirection();

//
//  Routes
//

app.MapExampleRoutes();

// Adding the SwaggerUI route
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.Run();
