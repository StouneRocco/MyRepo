/**
 * The services are classes that contains parts of the business
 * logic.
 * 
 * They are used to encapsulate the business logic and to make
 * the code more readable and maintainable.
 * 
 * They are injected into the controllers using the Dependency
 * Injection pattern.
 */

//
//  Imports
//

using Backend.Models;
using Backend.BLL.Interfaces;

namespace Backend.BLL.Services;

//
//  Class
//

public class ExampleService: IExampleService {

    public ExempleUser GetExempleUser(string name) {
        return new ExempleUser {
            Id = Guid.NewGuid(),
            Name = name
        };
    }
}