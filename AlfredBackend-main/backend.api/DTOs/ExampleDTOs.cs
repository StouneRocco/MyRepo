/**
 * This class is meant to validate the input from the example
 * hello world route.
 * 
 * Check how annotations works to understand.
 * 
 * Also there are many annotations so check the ones that
 * correspond to your case. For instance, there is a special
 * annotation for email [EmailAddress(ErrorMessage = "Invalid email !")],
 * for the parameters coming from a GET quey then you need to use the
 * [from_query], and they can be pilled up.
 */

//
//  Imports
//

using System.ComponentModel.DataAnnotations;
using Microsoft.AspNetCore.Mvc;

/**
 * 
 */
namespace Backend.API.DTOs;

//
//  Class
//

public sealed class GetHelloWorldDTO {
    [FromQuery]
    [Required(ErrorMessage = "The name is needed !")]
    [MinLength(1, ErrorMessage = "The name must not be empty !")]
    public string Name { get; init; } = string.Empty;
}