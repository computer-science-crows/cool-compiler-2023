from errors import SemanticError, AttributeError
from enviroment import Environment
from ast_ import Class, Attribute, Id, Type

class TypeChecker:
    def __init__(self, ast_root, class_references):
        """
        Initialize the TypeChecker.

        Args:
            ast_root: The root node of the Abstract Syntax Tree (AST).
            class_references: A dictionary mapping class names to their corresponding types.

        Attributes:
            class_references: A dictionary mapping class names to their corresponding types.
            traversal_counter: A counter for assigning td and tf values during depth-first traversal.

        Returns:
            None
        """
        self.class_references = class_references
        self.traversal_counter = 0
        self._initialize_order(ast_root, Environment())

    def _initialize_order(self, current_node, current_environment):
        """
        Initialize the order (td and tf) during depth-first traversal.

        Args:
            current_node: The current node in the AST.
            current_environment: The environment during AST traversal.

        Returns:
            None
        """
        # Increment the traversal counter
        self.traversal_counter += 1
        current_node.td = self.traversal_counter

        # Traverse methods in the current class
        for method_name, method_ref in current_node.methods.items():
            # Check for compatibility with inherited methods
            old_method = current_environment.get(method_name)

            if old_method and old_method.get_signature() != method_ref.get_signature():
                raise SemanticError(
                    method_ref.id.line,
                    method_ref.id.col,
                    f'{method_ref} of {current_node} is not compatible with {old_method} for inheritance'
                )

            # Define the method in the environment
            current_environment.define(method_name, method_ref)

            # Precalculate static type of formals before doing visitor
            for formal in method_ref.formal_list:
                if formal.type.value == 'Self_Type':
                    raise SemanticError(
                        formal.type.line,
                        formal.type.col,
                        f'Tried to declare {formal} with {formal.type}'
                    )

                formal.set_static_type(self._get_correct_type(formal, current_node.self_type))

        # Traverse children nodes
        for child_node in current_node.children:
            child_node.parent = current_node
            child_node.level = current_node.level + 1

            self._initialize_order(child_node, Environment(current_environment))

        # Set the tf value for the current node
        current_node.tf = self.traversal_counter

    def _is_order_conform(self, node_u, node_v):
        """
        Check if the traversal order of node_u conforms to the order of node_v.

        Args:
            node_u: The first node.
            node_v: The second node.

        Returns:
            bool: True if node_u conforms to node_v in the traversal order, False otherwise.
        """
        return node_v.td <= node_u.td <= node_v.tf

    def _find_least_common_ancestor(self, node_u, node_v):
        """
        Find the least common ancestor of two nodes in the AST.

        Args:
            node_u: The first node.
            node_v: The second node.

        Returns:
            Node: The least common ancestor node.
        """
        while node_u.type.value != node_v.type.value:
            if node_u.level > node_v.level:
                node_u = node_u.parent
            else:
                node_v = node_v.parent

        return node_u

    def _find_method_in_hierarchy(self, class_node, method_name):
        """
        Find the method in the class hierarchy.

        Args:
            class_node: The class node.
            method_name: The name of the method to find.

        Returns:
            Method: The found method or None if not found.
        """
        while class_node and method_name not in class_node.methods:
            class_node = class_node.parent

        return class_node.methods[method_name] if class_node else None

    def _get_correct_type_for_node(self, node, default_type):
        """
        Get the correct type for a given node.

        Args:
            node: The node for which to determine the correct type.
            default_type: The default type to use if the node's type is 'Self_Type'.

        Returns:
            Type: The correct type for the node.
        """
        if node.type.value == 'Self_Type':
            return default_type

        if node.type.value not in self.class_references:
            raise TypeError(node.type.line, node.type.col, f'{Class(node.type)} does not exist')

        return self.class_references[node.type.value]

    # Visitor pattern
    def visit(self, node):
        """
        Dispatch method for visiting different AST node types.

        Args:
            node: The AST node to visit.

        Returns:
            The result of visiting the AST node.
        """
        try:
            method_name = 'visit_' + node.__class__.__name__
            visit_method = getattr(self, method_name)
            return visit_method(node)
        except:
            raise AttributeError(node.type.line, node.type.col, f'Visit method not implemented for node type: {node.__class__.__name__}')

    # Atomic Expressions
    def visit_Int(self, node):
        node.set_static_type(self.class_references['Int'])

    def visit_String(self, node):
        node.set_static_type(self.class_references['String'])

    def visit_Bool(self, node):
        node.set_static_type(self.class_references['Bool'])

    def visit_Id(self, node):
        ref = self.current_environment.get(node.value)

        if not ref:
            raise NameError(node.line, node.col, f'{node} does not exist in this environment')

        node.set_static_type(self._get_correct_type_for_node(ref, self.current_class.self_type))

    def visit_New(self, node):
        node.set_static_type(self._get_correct_type_for_node(node, self.current_class.self_type))

    # Arithmetic Operations
    def visit_Plus(self, node):
        self.visit(node.left)
        self.visit(node.right)

        if node.left.static_type.type.value != 'Int' or node.right.static_type.type.value != 'Int':
            raise TypeError(node.line, node.col, f'{node.left} and {node.right} must both have {self.class_references["Int"]}')

        node.set_static_type(self.class_references['Int'])

    def visit_Minus(self, node):
        self.visit_Plus(node)

    def visit_Mult(self, node):
        self.visit_Plus(node)

    def visit_Div(self, node):
        self.visit_Plus(node)

    # Comparison Operations
    def visit_Eq(self, node):
        self.visit(node.left)
        self.visit(node.right)

        types = ['Int', 'String', 'Bool']

        lft_type = node.left.static_type.type.value
        rgt_type = node.right.static_type.type.value

        if lft_type in types or rgt_type in types:
            if lft_type != rgt_type:
                raise TypeError(node.line, node.col, f'{node.left} with {node.left.static_type} and {node.right} with {node.right.static_type} must both have the same type')

        node.set_static_type(self.class_references['Bool'])

    def visit_Less(self, node):
        self.visit(node.left)
        self.visit(node.right)

        if node.left.static_type.type.value != 'Int' or node.right.static_type.type.value != 'Int':
            raise TypeError(node.line, node.col, f'{node.left} and {node.right} must both have {self.class_references["Int"]}')

        node.set_static_type(self.class_references['Bool'])

    def visit_LessEq(self, node):
        self.visit_Less(node)

    # Unary Operations
    def visit_Not(self, node):
        self.visit(node.expr)

        if node.expr.static_type.type.value != 'Bool':
            raise TypeError(node.expr.line, node.expr.col, f'{node.expr} must have {self.class_references["Bool"]}')

        node.set_static_type(self.class_references['Bool'])

    def visit_IsVoid(self, node):
        self.visit(node.expr)

        node.set_static_type(self.class_references['Bool'])
    
    def visit_IntComp(self, node):
        self.visit(node.expr)

        if node.expr.static_type.type.value != 'Int':
            raise TypeError(node.line, node.col, f'{node.expr} must have {self.class_references["Int"]}')

        node.set_static_type(self.class_references['Int'])

    # Control Flow Operations
    def visit_If(self, node):
        self.visit(node.predicate)

        predicate_type = node.predicate.static_type

        if predicate_type.type.value != 'Bool':
            raise TypeError(node.predicate.line, node.predicate.col, f'{node} predicate must have {self.class_references["Bool"]}, not {predicate_type}')

        self.visit(node.if_branch)
        self.visit(node.else_branch)

        node.set_static_type(self._find_least_common_ancestor(node.if_branch.static_type, node.else_branch.static_type))

    def visit_While(self, node):
        self.visit(node.predicate)

        predicate_type = node.predicate.static_type

        if predicate_type.type.value != 'Bool':
            raise TypeError(node.predicate.line, node.predicate.col, f'{node} predicate must have {self.class_references["Bool"]}, not {predicate_type}')

        self.visit(node.body)

        node.set_static_type(self.class_references['Object'])

    # Let Expression
    def visit_LetVar(self, node):
        if node.id.value == 'self':
            raise SemanticError(node.id.line, node.id.col, f'Tried to assign to {node.id}')

        if node.opt_expr_init:
            self.logger.info(f'{node} has expr')

            expr = node.opt_expr_init
            self.visit(expr)

            self.cur_env.define(node.id.value, node)
            self.visit(node.id)
            node.set_static_type(node.id.static_type)

            if not self._is_order_conform(expr.static_type, node.static_type):
                raise TypeError(node.line, node.col, f'{expr} with {expr.static_type} doesnt conform to {node} with {node.static_type}')

        else:
            self.cur_env.define(node.id.value, node)
            self.visit(node.id)
            node.set_static_type(node.id.static_type)

    def visit_Let(self, node):
        old_env = self.cur_env
        self.cur_env = Environment(old_env)

        for let_var in node.let_list:
            self.visit(let_var)

        self.visit(node.body)
        node.set_static_type(node.body.static_type)

        self.cur_env = old_env

    # Case Expression
    def visit_CaseVar(self, node):
        if node.id.value == 'self':
            raise SemanticError(node.id.line, node.id.col, f'Tried to assign to {node.id}')

        if node.type.value == 'SELF_TYPE':
            raise SemanticError(node.type.line, node.type.col, f'Tried to declare {node} with {node.type}')
        
        self.cur_env.define(node.id.value, node)
        self.visit(node.id)
        node.set_static_type(node.id.static_type)

    def visit_Case(self, node):
        self.visit(node.expr)

        type_set = set()
        lca = None

        for branch in node.case_list:
            if branch.case_var.type.value in type_set:
                raise SemanticError(branch.case_var.type.line, branch.case_var.type.col, f'{branch.case_var.type} appears in other branch of {node}')

            type_set.add(branch.case_var.type.value)

            old_env = self.cur_env
            self.cur_env = Environment(old_env)

            self.visit(branch.case_var)
            self.visit(branch.expr)

            if not lca:
                lca = branch.expr.static_type

            else: lca = self._find_least_common_ancestor(lca, branch.expr.static_type)

            self.cur_env = old_env

        node.set_static_type(lca)

    # Dispatch Operation
    def visit_Dispatch(self, node):
        pass

    # Assignment Operation
    def visit_Assignment(self, node):
        pass
    def visit_Block(self, node):
        pass

    # Self Type Handling
    def visit_Self_Type(self, node):
        pass

    # Class Definition
    def visit_Class(self, node):
        """
        Visit method for handling Class nodes.

        Args:
            node: The Class node.

        Returns:
            The result of visiting the Class node.
        """
        old_environment = self.current_environment
        self.current_environment = Environment(old_environment)

        old_class = self.current_class
        self.current_class = node

        self.current_environment.define('self', Attribute(Id('self'), Type('Self_Type'), None))

        for feature in node.feature_list:
            if isinstance(feature, Attribute):
                if self.current_environment.get(feature.id.value):
                    raise SemanticError(feature.id.line, feature.id.col, f'Tried to redefine {feature} by inheritance')

                self.current_environment.define(feature.id.value, feature)

        for feature in node.feature_list:
            self.visit(feature)

        for cls in node.children:
            self.visit(cls)

        self.current_environment = old_environment
        self.current_class = old_class

    def visit_Method(self, method_node):
        # Handle type checking for Method nodes
        # ...
        pass 

    def visit_Attribute(self, attribute_node):
        # Handle type checking for Attribute nodes
        # ...
        pass 
    
    def visit_Formal(self, formal_node):
        # Handle type checking for Formal nodes
        # ...
        pass 
    
    def perform_type_checking(self):
        # Entry point for type checking
        # ...
        pass 
