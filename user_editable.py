user_dict = {

    'prompt_instruction' : """You are provided with two distinct text inputs separated by markers in the following format:
        ### [TITLE] ###

            Input 1: "Job Description to be Transformed" - the current job description that needs updating.
            Input 2: "Reference Material" - supporting content that outlines relevant concepts and methodologies.

        Task:
        Transform each job description into a forward-thinking, AI-augmented version. For each task or section mentioned in the original job description, update it to include specific, actionable enhancements driven by AI. Leverage all reference materials to ensure that each updated task reflects cutting-edge AI methodologies and practices. Your final output should be a cohesive, detailed job description that outlines how AI will augment and transform the role's current responsibilities.

        Format:
        - Strictly separate each job description with "[DIVIDER]".
        - Remove the initial separation markers "### [TITLE] ###" in your output.""",

    'gpt_model' : 'gpt-4o-mini-2024-07-18',
    'gpt_input_limit' : 128000,
    'font' : 'Raleway'
       
}