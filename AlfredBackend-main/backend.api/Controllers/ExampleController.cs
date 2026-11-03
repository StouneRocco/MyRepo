/**
 * Controllers are classes that contain the logic of what
 * happens after the route is called.
 * 
 * They are meant to call the services and return the result
 * to the route. And also ask for parameters that are a DTO
 * from the route to validate the input.
 */

//
//  Imports
//

using Backend.API.DTOs;
using Backend.Models;
using Backend.BLL.Interfaces;

namespace Backend.API.Controllers;

//
//  Class
//

public class ExampleController(
    IExampleService _exampleService
) {

    /**
     * This function is called when the route is called.
     * 
     * It is named in a certain way. Get is the HTTP method,
     * HelloWorld is the name of the route, and the parameters
     * are the DTO from the route to validate the input.
     * 
     * @param hw The DTO from the route to validate the input.
     * @return The user with the given name.
     */
    public ExempleUser GetHelloWorld(GetHelloWorldDTO hw) {
        return _exampleService.GetExempleUser(
            hw.Name
        );
    }
}