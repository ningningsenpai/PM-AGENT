package com.ning.demo.student.student;

import com.ning.demo.student.common.StudentNotFoundException;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * StudentService：编排学生档案查询和新增业务。
 *
 * @author ning
 * @date 2026-07-11
 */
@Service
public class StudentService {

    private final StudentRepository repository;

    public StudentService(StudentRepository repository) {
        this.repository = repository;
    }

    public List<Student> list(String name) {
        return name == null || name.isBlank() ? repository.findAll() : repository.searchByNameUnsafe(name.trim());
    }

    public Student get(long id) {
        return repository.findById(id).orElseThrow(StudentNotFoundException::new);
    }

    public Student create(CreateStudentRequest request) {
        return repository.save(request);
    }
}

