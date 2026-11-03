/**
 * Just ot give an exemple of a route.
 * 
 * A route is the part of the application which exposes
 * and endpoint(ex: http://localhost:<PORT>/example/hello_world). This
 * allows the app to receive and send data through HTTP and HTTPS
 * protocols. The frontend comes to connect on these.
 */

//
//  Imports
//

using Backend.API.Controllers;
using Backend.API.DTOs;

namespace Backend.API.Routes;

//
//  Class
//

public static class ExampleRoutes {

    /**
     * Gives the definitions of the routes to the class which
     * implement IEndpointRouteBuilder.
     * 
     * It is meant to be used in Program.cs using the syntaxe:
     *  app.MapExampleRoutes()
     * 
     * It links the routes to main app giving access to it.
     * 
     * @param None thanks to 'this' -> Check what it is
     * @return Nothing
     */
    public static void MapExampleRoutes(this IEndpointRouteBuilder mainRouter) {
        var exampleRouter = mainRouter.MapGroup("/example");

        //
        //  Routes
        //
        
        /**
         * Route to show it works
         */
        exampleRouter.MapGet("/hello_world", (
            ExampleController controller,
            [AsParameters] GetHelloWorldDTO hw
        ) => {
            return controller.GetHelloWorld(hw);
        });
    }
}
