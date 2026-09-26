from app.infrastructure.database.schema import (
    initialize_database,
)

from app.recipes.compiler import (
    RecipeCompiler,
)


RUN_ID = (
    "d2cc3152-6244-4221-aa23-09dba2efb1c9"
)


def main():

    initialize_database()

    compiler = (
        RecipeCompiler()
    )

    result = (
        compiler.compile_run(
            RUN_ID
        )
    )

    print(
        "\n[Recipe Compiler Result]"
    )

    print(
        "Status:",
        result.status,
    )

    print(
        "Run ID:",
        result.run_id,
    )

    print(
        "Recipe ID:",
        result.recipe_id,
    )

    print(
        "Recipe name:",
        result.recipe_name,
    )

    print(
        "Recipe status:",
        result.recipe_status,
    )

    print(
        "Reason:",
        result.reason,
    )


if __name__ == "__main__":

    main()