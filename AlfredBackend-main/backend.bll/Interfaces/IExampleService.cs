/**
 * Interface for the ExampleService.
 * 
 * It is used to define the expected methods that the ExampleService
 * must implement.
 * 
 * It is meant to be used by the controllers.
 * 
 * It is injected into the controllers using the Dependency
 * Injection pattern.
 * 
 * And it existence is justified by the fact that if you want to
 * test a controller then you can easily mock the service and test
 * the controller without having to test the service.
 */

//
//  Imports
//

using Backend.Models;

namespace Backend.BLL.Interfaces;

//
//  Interface
//

public interface IExampleService {
    /**
     * Just a function to illustrate that the controller
     * gives a simple string and the service returns the
     * corresponding model. The exemple could be a calculator
     * for instance, this time the controller would give 2
     * numbers and the service would return the result of
     * the addition.
     * 
     * @param name The name of the user to get.
     * @return The user with the given name.
     */
    ExempleUser GetExempleUser(string name);
}