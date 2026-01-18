#include "plural_expression_parser.h"
#include <cctype>

// AST Node implementations

class NumberNode : public ASTNode {
public:
    explicit NumberNode(unsigned long value) : value_(value) {}
    unsigned long evaluate(unsigned long) const override { return value_; }
private:
    unsigned long value_;
};

class VariableNode :  public ASTNode {
public:
    unsigned long evaluate(unsigned long n) const override { return n; }
};

class BinaryOpNode : public ASTNode {
public:
    enum class Op { ADD, SUB, MUL, DIV, MOD, EQ, NE, LT, LE, GT, GE, AND, OR };

    BinaryOpNode(Op op, std::unique_ptr<ASTNode> left, std:: unique_ptr<ASTNode> right)
        : op_(op), left_(std::move(left)), right_(std::move(right)) {}

    unsigned long evaluate(unsigned long n) const override {
        unsigned long left_val = left_->evaluate(n);
        unsigned long right_val = right_->evaluate(n);

        switch (op_) {
            case Op::ADD: return left_val + right_val;
            case Op::SUB: return left_val - right_val;
            case Op::MUL: return left_val * right_val;
            case Op::DIV:  return right_val != 0 ? left_val / right_val : 0;
            case Op::MOD: return right_val != 0 ?  left_val % right_val :  0;
            case Op:: EQ:   return left_val == right_val ?  1 : 0;
            case Op::NE:  return left_val != right_val ? 1 : 0;
            case Op::LT:   return left_val < right_val ? 1 : 0;
            case Op::LE:  return left_val <= right_val ? 1 : 0;
            case Op::GT:  return left_val > right_val ? 1 : 0;
            case Op::GE:  return left_val >= right_val ? 1 :  0;
            case Op:: AND: return (left_val && right_val) ? 1 : 0;
            case Op::OR:  return (left_val || right_val) ? 1 : 0;
        }
        return 0;
    }

private:
    Op op_;
    std::unique_ptr<ASTNode> left_;
    std::unique_ptr<ASTNode> right_;
};

class UnaryOpNode : public ASTNode {
public:
    enum class Op { NOT, NEG };

    UnaryOpNode(Op op, std:: unique_ptr<ASTNode> operand)
        : op_(op), operand_(std::move(operand)) {}

    unsigned long evaluate(unsigned long n) const override {
        unsigned long val = operand_->evaluate(n);
        switch (op_) {
            case Op::NOT: return !val ?  1 : 0;
            case Op::NEG: return -val;
        }
        return 0;
    }

private:
    Op op_;
    std::unique_ptr<ASTNode> operand_;
};

class TernaryNode : public ASTNode {
public:
    TernaryNode(std::unique_ptr<ASTNode> condition,
                std::unique_ptr<ASTNode> true_expr,
                std::unique_ptr<ASTNode> false_expr)
        : condition_(std::move(condition))
        , true_expr_(std::move(true_expr))
        , false_expr_(std:: move(false_expr)) {}

    unsigned long evaluate(unsigned long n) const override {
        unsigned long cond = condition_->evaluate(n);
        return cond ? true_expr_->evaluate(n) : false_expr_->evaluate(n);
    }

private:
    std::unique_ptr<ASTNode> condition_;
    std::unique_ptr<ASTNode> true_expr_;
    std::unique_ptr<ASTNode> false_expr_;
};

// PluralExpressionParser implementation

PluralExpressionParser:: PluralExpressionParser()
    : current_(0)
    , has_error_(false) {
}

PluralExpressionParser::~PluralExpressionParser() {
}

std::vector<Token> PluralExpressionParser::tokenize(const std::string& expr) {
    std::vector<Token> tokens;
    size_t i = 0;

    while (i < expr.length()) {
        char c = expr[i];

        // Skip whitespace
        if (std::isspace(c)) {
            i++;
            continue;
        }

        // Numbers
        if (std::isdigit(c)) {
            unsigned long value = 0;
            while (i < expr.length() && std::isdigit(expr[i])) {
                value = value * 10 + (expr[i] - '0');
                i++;
            }
            tokens.emplace_back(TokenType::NUMBER, value);
            continue;
        }

        // Variable 'n'
        if (c == 'n') {
            tokens.emplace_back(TokenType::VARIABLE);
            i++;
            continue;
        }

        // Two-character operators
        if (i + 1 < expr.length()) {
            std::string two_char = expr.substr(i, 2);
            if (two_char == "==") {
                tokens.emplace_back(TokenType::EQUAL);
                i += 2;
                continue;
            } else if (two_char == "!=") {
                tokens.emplace_back(TokenType::NOT_EQUAL);
                i += 2;
                continue;
            } else if (two_char == "<=") {
                tokens.emplace_back(TokenType::LESS_EQUAL);
                i += 2;
                continue;
            } else if (two_char == ">=") {
                tokens.emplace_back(TokenType::GREATER_EQUAL);
                i += 2;
                continue;
            } else if (two_char == "&&") {
                tokens.emplace_back(TokenType::AND);
                i += 2;
                continue;
            } else if (two_char == "||") {
                tokens.emplace_back(TokenType::OR);
                i += 2;
                continue;
            }
        }

        // Single-character operators
        switch (c) {
            case '+': tokens.emplace_back(TokenType::PLUS); break;
            case '-': tokens.emplace_back(TokenType:: MINUS); break;
            case '*': tokens.emplace_back(TokenType::MULTIPLY); break;
            case '/': tokens.emplace_back(TokenType:: DIVIDE); break;
            case '%': tokens.emplace_back(TokenType::MODULO); break;
            case '<': tokens.emplace_back(TokenType:: LESS); break;
            case '>': tokens.emplace_back(TokenType::GREATER); break;
            case '!': tokens.emplace_back(TokenType::NOT); break;
            case '?': tokens.emplace_back(TokenType::QUESTION); break;
            case ':': tokens.emplace_back(TokenType:: COLON); break;
            case '(': tokens.emplace_back(TokenType::LPAREN); break;
            case ')': tokens.emplace_back(TokenType::RPAREN); break;
            default:
                // Unknown character, skip it
                break;
        }
        i++;
    }

    tokens.emplace_back(TokenType::END);
    return tokens;
}

bool PluralExpressionParser::parse(const std::string& expression) {
    tokens_ = tokenize(expression);
    current_ = 0;
    has_error_ = false;
    error_message_.clear();
    root_ = nullptr;

    root_ = parseExpression();
    return root_ != nullptr && !has_error_;
}

unsigned long PluralExpressionParser::evaluate(unsigned long n) const {
    if (! root_) {
        return 0;
    }
    return root_->evaluate(n);
}

Token PluralExpressionParser:: peek() const {
    if (current_ < tokens_.size()) {
        return tokens_[current_];
    }
    return Token(TokenType::END);
}

Token PluralExpressionParser::consume() {
    if (current_ < tokens_.size()) {
        return tokens_[current_++];
    }
    return Token(TokenType::END);
}

bool PluralExpressionParser:: match(TokenType type) {
    if (check(type)) {
        consume();
        return true;
    }
    return false;
}

bool PluralExpressionParser::check(TokenType type) const {
    return peek().type == type;
}

void PluralExpressionParser::setError(const std:: string& message) {
    has_error_ = true;
    error_message_ = message;
}

std::unique_ptr<ASTNode> PluralExpressionParser::parseExpression() {
    return parseTernary();
}

std::unique_ptr<ASTNode> PluralExpressionParser::parseTernary() {
    auto expr = parseLogicalOr();
    if (!expr) {
        return nullptr;
    }

    if (match(TokenType::QUESTION)) {
        auto true_expr = parseExpression();
        if (!true_expr) {
            return nullptr;
        }

        if (!match(TokenType:: COLON)) {
            setError("Expected ':' in ternary expression");
            return nullptr;
        }

        auto false_expr = parseTernary();
        if (!false_expr) {
            return nullptr;
        }

        return std::make_unique<TernaryNode>(std::move(expr),
                                             std::move(true_expr),
                                             std::move(false_expr));
    }

    return expr;
}

std::unique_ptr<ASTNode> PluralExpressionParser::parseLogicalOr() {
    auto left = parseLogicalAnd();
    if (!left) {
        return nullptr;
    }

    while (match(TokenType::OR)) {
        auto right = parseLogicalAnd();
        if (!right) {
            return nullptr;
        }
        left = std::make_unique<BinaryOpNode>(BinaryOpNode::Op::OR,
                                              std::move(left),
                                              std::move(right));
    }

    return left;
}

std::unique_ptr<ASTNode> PluralExpressionParser::parseLogicalAnd() {
    auto left = parseEquality();
    if (!left) {
        return nullptr;
    }

    while (match(TokenType::AND)) {
        auto right = parseEquality();
        if (!right) {
            return nullptr;
        }
        left = std::make_unique<BinaryOpNode>(BinaryOpNode:: Op::AND,
                                              std::move(left),
                                              std::move(right));
    }

    return left;
}

std::unique_ptr<ASTNode> PluralExpressionParser::parseEquality() {
    auto left = parseRelational();
    if (!left) {
        return nullptr;
    }

    while (true) {
        if (match(TokenType::EQUAL)) {
            auto right = parseRelational();
            if (!right) {
                return nullptr;
            }
            left = std::make_unique<BinaryOpNode>(BinaryOpNode::Op::EQ,
                                                  std::move(left),
                                                  std::move(right));
        } else if (match(TokenType::NOT_EQUAL)) {
            auto right = parseRelational();
            if (!right) {
                return nullptr;
            }
            left = std::make_unique<BinaryOpNode>(BinaryOpNode::Op::NE,
                                                  std::move(left),
                                                  std::move(right));
        } else {
            break;
        }
    }

    return left;
}

std::unique_ptr<ASTNode> PluralExpressionParser::parseRelational() {
    auto left = parseAdditive();
    if (!left) {
        return nullptr;
    }

    while (true) {
        if (match(TokenType::LESS)) {
            auto right = parseAdditive();
            if (!right) {
                return nullptr;
            }
            left = std::make_unique<BinaryOpNode>(BinaryOpNode::Op::LT,
                                                  std::move(left),
                                                  std::move(right));
        } else if (match(TokenType::LESS_EQUAL)) {
            auto right = parseAdditive();
            if (!right) {
                return nullptr;
            }
            left = std::make_unique<BinaryOpNode>(BinaryOpNode::Op::LE,
                                                  std:: move(left),
                                                  std::move(right));
        } else if (match(TokenType::GREATER)) {
            auto right = parseAdditive();
            if (!right) {
                return nullptr;
            }
            left = std::make_unique<BinaryOpNode>(BinaryOpNode::Op::GT,
                                                  std::move(left),
                                                  std:: move(right));
        } else if (match(TokenType:: GREATER_EQUAL)) {
            auto right = parseAdditive();
            if (!right) {
                return nullptr;
            }
            left = std::make_unique<BinaryOpNode>(BinaryOpNode::Op::GE,
                                                  std::move(left),
                                                  std::move(right));
        } else {
            break;
        }
    }

    return left;
}

std:: unique_ptr<ASTNode> PluralExpressionParser:: parseAdditive() {
    auto left = parseMultiplicative();
    if (!left) {
        return nullptr;
    }

    while (true) {
        if (match(TokenType::PLUS)) {
            auto right = parseMultiplicative();
            if (!right) {
                return nullptr;
            }
            left = std::make_unique<BinaryOpNode>(BinaryOpNode::Op::ADD,
                                                  std::move(left),
                                                  std::move(right));
        } else if (match(TokenType:: MINUS)) {
            auto right = parseMultiplicative();
            if (!right) {
                return nullptr;
            }
            left = std::make_unique<BinaryOpNode>(BinaryOpNode::Op::SUB,
                                                  std::move(left),
                                                  std::move(right));
        } else {
            break;
        }
    }

    return left;
}

std:: unique_ptr<ASTNode> PluralExpressionParser:: parseMultiplicative() {
    auto left = parseUnary();
    if (!left) {
        return nullptr;
    }

    while (true) {
        if (match(TokenType::MULTIPLY)) {
            auto right = parseUnary();
            if (!right) {
                return nullptr;
            }
            left = std::make_unique<BinaryOpNode>(BinaryOpNode::Op::MUL,
                                                  std::move(left),
                                                  std::move(right));
        } else if (match(TokenType::DIVIDE)) {
            auto right = parseUnary();
            if (!right) {
                return nullptr;
            }
            left = std::make_unique<BinaryOpNode>(BinaryOpNode::Op::DIV,
                                                  std:: move(left),
                                                  std::move(right));
        } else if (match(TokenType::MODULO)) {
            auto right = parseUnary();
            if (!right) {
                return nullptr;
            }
            left = std::make_unique<BinaryOpNode>(BinaryOpNode::Op::MOD,
                                                  std::move(left),
                                                  std::move(right));
        } else {
            break;
        }
    }

    return left;
}

std::unique_ptr<ASTNode> PluralExpressionParser::parseUnary() {
    if (match(TokenType::NOT)) {
        auto operand = parseUnary();
        if (!operand) {
            return nullptr;
        }
        return std::make_unique<UnaryOpNode>(UnaryOpNode::Op::NOT, std::move(operand));
    }

    if (match(TokenType:: MINUS)) {
        auto operand = parseUnary();
        if (!operand) {
            return nullptr;
        }
        return std::make_unique<UnaryOpNode>(UnaryOpNode:: Op::NEG, std::move(operand));
    }

    return parsePrimary();
}

std::unique_ptr<ASTNode> PluralExpressionParser::parsePrimary() {
    // Number
    if (check(TokenType::NUMBER)) {
        Token tok = consume();
        return std::make_unique<NumberNode>(tok.value);
    }

    // Variable 'n'
    if (match(TokenType::VARIABLE)) {
        return std::make_unique<VariableNode>();
    }

    // Parenthesized expression
    if (match(TokenType::LPAREN)) {
        auto expr = parseExpression();
        if (!expr) {
            return nullptr;
        }

        if (!match(TokenType:: RPAREN)) {
            setError("Expected ')' after expression");
            return nullptr;
        }
        return expr;
    }

    setError("Unexpected token in expression");
    return nullptr;
}
