/**
 * This files stores the models for the example feature.
 * 
 * The models are classes with just propertiers nothing else.
 * 
 * It is used every where in the app therefore we cheat a beat
 * on the architecture so that every layers imports it and
 * use it instead of having to define the same class as many
 * times have we have layers in the solution.
 * 
 * You should check what the syntaxe { get; set; } corresponds to.
 */

//
//  Imports
//

namespace Backend.Models;

//
//  Class
//

public class ExempleUser {
    public Guid Id { get; set; } // If you dont know what Guid check online
    public required string Name { get; set; }
}