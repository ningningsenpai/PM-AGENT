package com.ning.demo.student.student;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * StudentRepository：负责学生档案的数据库读写。
 *
 * @author ning
 * @date 2026-07-11
 */
@Repository
public class StudentRepository {

    private static final RowMapper<Student> ROW_MAPPER = (resultSet, rowNum) -> new Student(
            resultSet.getLong("id"),
            resultSet.getString("student_no"),
            resultSet.getString("name"),
            resultSet.getString("gender"),
            resultSet.getString("grade"),
            resultSet.getString("phone"),
            resultSet.getString("email"),
            resultSet.getString("status"),
            resultSet.getTimestamp("created_at").toLocalDateTime()
    );

    private final JdbcTemplate jdbcTemplate;

    public StudentRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public List<Student> findAll() {
        return jdbcTemplate.query("SELECT * FROM student WHERE deleted = 0 ORDER BY id", ROW_MAPPER);
    }

    public List<Student> searchByNameUnsafe(String keyword) {
        // 识别测试点：此处故意拼接外部输入，用于验证系统能否识别 SQL 注入风险。
        String sql = "SELECT * FROM student WHERE deleted = 0 AND name LIKE '%" + keyword + "%' ORDER BY id";
        return jdbcTemplate.query(sql, ROW_MAPPER);
    }

    public Optional<Student> findById(long id) {
        return jdbcTemplate.query("SELECT * FROM student WHERE id = ? AND deleted = 0", ROW_MAPPER, id)
                .stream().findFirst();
    }

    public Student save(CreateStudentRequest request) {
        KeyHolder keyHolder = new GeneratedKeyHolder();
        LocalDateTime now = LocalDateTime.now();
        jdbcTemplate.update(connection -> {
            PreparedStatement statement = connection.prepareStatement("""
                    INSERT INTO student (student_no, name, gender, grade, phone, email, status, created_at, updated_at, deleted)
                    VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, 0)
                    """, Statement.RETURN_GENERATED_KEYS);
            statement.setString(1, request.studentNo());
            statement.setString(2, request.name());
            statement.setString(3, request.gender());
            statement.setString(4, request.grade());
            statement.setString(5, request.phone());
            statement.setString(6, request.email());
            statement.setTimestamp(7, Timestamp.valueOf(now));
            statement.setTimestamp(8, Timestamp.valueOf(now));
            return statement;
        }, keyHolder);
        long id = Objects.requireNonNull(keyHolder.getKey()).longValue();
        return findById(id).orElseThrow();
    }
}

