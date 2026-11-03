/**
 * Depency injection file.
 * 
 * It is declared in Program.cs as a Scope.
 * 
 * Here every interface that you add thanks to the method
 * AddScoped will be injected with the requested class.
 * 
 * It meants, that for instance if you have a repository and that a certain  
 * service or else needs it (meaning that the repository is in its class        
 * constructor args), if you ask for a certain IRepository in the constructot  
 * (interface of the required repository) then when the repository will be     
 * asked in a service or else then a Repository respecting the IRepository       
 * contract will be created and injected in the service or else. Therefore, no  
 * need to pass the repository arg to the service or else when creating it.
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

using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace Backend.DAL;

//
//  Class
//

public static class DependencyInjection {
    public static IServiceCollection AddDAL(this IServiceCollection services) {
        // Registering the db : temporary connexion string hardcoded TODO
        // TODO : commented for now cause of unknown used tech
        // services.AddDbContext<AppDbContext>(
        //     options => options.UseNpgsql("")
        // );


        // services.AddScoped<Interface, Class(implementating the interface)>();
        // ex : services.AddScoped<IRepository, Repository>();
        // 
        // Here the Repository class should implement the IRepository interface, and if
        // a service or else needs the repository, then it will be automatically given to
        // it no need to pass it.
        //
        // The purpose here is to have the cleanest objects possible -> Every time that
        // you need a repository or any other objects then it has the fewest args to be
        // passed to it, just the logic ones, like the n_iteration or stuff like that.   

        //
        //  Repositories registry
        //

        return services;
    }
}
