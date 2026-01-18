#pragma once

#include <string>
#include <memory>
#include <vector>

// Token types for the plural expression language
enum class TokenType {
    NUMBER,
    VARIABLE,      // 'n'
    PLUS,          // +
    MINUS,         // -
    MULTIPLY,      // *
    DIVIDE,        // /
    MODULO,        // %
    EQUAL,         // ==
    NOT_EQUAL,     // !=
    LESS,          // <
    LESS_EQUAL,    // <=
    GREATER,       // >
    GREATER_EQUAL, // >=
    AND,           // &&
    OR,            // ||
    NOT,           // !
    QUESTION,      // ?
    COLON,         // :
    LPAREN,        // (
    RPAREN,        // )
    END
};

struct Token {
    TokenType type;
    unsigned long value;  // For NUMBER tokens

    Token(TokenType t, unsigned long v = 0) : type(t), value(v) {}
};

// Abstract syntax tree node
class ASTNode {
public:
    virtual ~ASTNode() = default;
    virtual unsigned long evaluate(unsigned long n) const = 0;
};

class PluralExpressionParser {
public:
    PluralExpressionParser();
    ~PluralExpressionParser();

    // Parse a plural expression string
    bool parse(const std::string& expression);

    // Evaluate the parsed expression for a given n
    unsigned long evaluate(unsigned long n) const;

    // Check if expression is valid
    bool isValid() const { return root_ != nullptr && !has_error_; }

    // Get error message if parsing failed
    const std::string& getError() const { return error_message_; }

private:
    // Tokenizer
    std::vector<Token> tokenize(const std::string& expr);

    // Recursive descent parser (returns nullptr on error)
    std::unique_ptr<ASTNode> parseExpression();
    std::unique_ptr<ASTNode> parseTernary();
    std::unique_ptr<ASTNode> parseLogicalOr();
    std::unique_ptr<ASTNode> parseLogicalAnd();
    std::unique_ptr<ASTNode> parseEquality();
    std::unique_ptr<ASTNode> parseRelational();
    std::unique_ptr<ASTNode> parseAdditive();
    std::unique_ptr<ASTNode> parseMultiplicative();
    std::unique_ptr<ASTNode> parseUnary();
    std::unique_ptr<ASTNode> parsePrimary();

    // Helper methods
    Token peek() const;
    Token consume();
    bool match(TokenType type);
    bool check(TokenType type) const;
    void setError(const std::string& message);

    std::vector<Token> tokens_;
    size_t current_;
    std::unique_ptr<ASTNode> root_;
    bool has_error_;
    std:: string error_message_;
};
