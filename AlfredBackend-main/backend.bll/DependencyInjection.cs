/**
 * Depency injection file.
 * 
 * It is declared in Program.cs as a Scope.
 * 
 * Here every interface that you add thanks to the method
 * AddScoped will be injected with the requested class.
 * 
 * It meants, that for instance if you have a service and that a certain  
 * controller or else needs it (meaning that the service is in its class        
 * constructor args), if you ask for a certain IService in the constructot  
 * (interface of the required service) then when the service will be     
 * asked in a controller or else then a Service respecting the IService       
 * contract will be created and injected in the controller or else. Therefore, no  
 * need to pass the service arg to the controller or else when creating it.
 * 
 * The goals of dependency injection are:
 *   - To provide objects with their dependencies instead of having
 *     them create those dependencies themselves.
 *   - To reduce coupling to concrete implementations, making
 *     dependencies easier to replace and code easier to test.
 *
 * Using a dependency injection also allows us:
 *   - To centralise dependency registration and manage instance
 *     lifetimes, such as singleton, scoped, and transient.
 *   - To automatically construct dependency graphs, avoiding
 *     repetitive manual object creation and wiring.
 */

using Microsoft.Extensions.DependencyInjection;
using Backend.BLL.Interfaces;
using Backend.BLL.Services;

namespace Backend.BLL;

//
//  Class
//

public static class DependencyInjection {

    public static IServiceCollection AddBLL(this IServiceCollection services) {
        // services.AddScoped<Interface, Class(implementating the interface)>();
        // ex : services.AddScoped<IService, Service>();
        // 
        // Here the Service class should implement the IService interface, and if
        // a controller or else needs the service, then it will be automatically given to
        // it no need to pass it.
        //
        // The purpose here is to have the cleanest objects possible -> Every time that
        // you need a service or any other objects then it has the fewest args to be
        // passed to it, just the logic ones, like the n_iteration or stuff like that.  

        //
        //  Services registry
        //

        services.AddScoped<IExampleService, ExampleService>();

        return services;
    }
}
